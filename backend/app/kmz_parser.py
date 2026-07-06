import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}
KML_URI = "http://www.opengis.net/kml/2.2"

POINT_PATTERN = re.compile(r"точка|point", re.IGNORECASE)
CACHE_PATTERN = re.compile(r"схрон|cache", re.IGNORECASE)
KT_POINT_PATTERN = re.compile(r"^КТ\s*\d+", re.IGNORECASE)
POST_PATTERN = re.compile(r"^пост[-\s]?\d+", re.IGNORECASE)
MERTVYAK_PATTERN = re.compile(r"мертвяк", re.IGNORECASE)
CACHE_OBJECT_PATTERN = re.compile(r"пост|мертвяк", re.IGNORECASE)
# Исключаем базы/старты только в файлах схронов (задача 3)
LANDMARK_EXCLUDE_IN_CACHE_FILES = re.compile(r"база|точка\s+старта|^\s*старт", re.IGNORECASE)

TASK1_FILE_HINT = re.compile(r"задача\s*1", re.IGNORECASE)
TASK2_FILE_HINT = re.compile(r"задача[-\s]*2", re.IGNORECASE)
TASK3_FILE_HINT = re.compile(r"задача\s*3|задача-3", re.IGNORECASE)
LK_FILE_HINT = re.compile(r"лк", re.IGNORECASE)
SBG_FILE_HINT = re.compile(r"сбг", re.IGNORECASE)

STAGE_LABELS: dict[int, str] = {
  1: "Захват КТ",
  2: "Поиск лута",
  3: "Штурм постов",
}

FILM_LOOT_PATTERN = re.compile(r"ящик|лут|пленк|плёнк|проход", re.IGNORECASE)
BOX_DIRECT_PATTERN = re.compile(r"ящик", re.IGNORECASE)
FILM_PASSAGE_PATTERN = re.compile(r"проход|пленк|плёнк", re.IGNORECASE)


def loot_variant_from_name(name: str) -> str:
  n = name.lower()
  if FILM_PASSAGE_PATTERN.search(n):
    return "film_passage"
  if BOX_DIRECT_PATTERN.search(n):
    return "box_direct"
  return "film_passage"


@dataclass
class ParsedPoint:
  name: str
  lat: float
  lon: float
  stage: int = 1


@dataclass
class ParsedCache:
  name: str
  lat: float
  lon: float
  team_side: str | None = None
  stage: int = 3
  cache_kind: str = "post"
  loot_variant: str = "film_passage"


@dataclass
class ParsedLandmark:
  name: str
  lat: float
  lon: float
  kind: str  # base | start | base_start
  team_side: str


def _find(el: ET.Element, tag: str) -> ET.Element | None:
  for candidate in (
    el.find(f"kml:{tag}", KML_NS),
    el.find(f"{{{KML_URI}}}{tag}"),
    el.find(tag),
  ):
    if candidate is not None:
      return candidate
  return None


def _find_coordinates(placemark: ET.Element) -> ET.Element | None:
  for candidate in (
    placemark.find(f".//{{{KML_URI}}}coordinates"),
    placemark.find(".//kml:coordinates", KML_NS),
    placemark.find(".//coordinates"),
  ):
    if candidate is not None:
      return candidate
  return None


def _placemarks(root: ET.Element) -> list[ET.Element]:
  items = root.findall(f".//{{{KML_URI}}}Placemark")
  if not items:
    items = root.findall(".//kml:Placemark", KML_NS)
  if not items:
    items = root.findall(".//Placemark")
  return list(items)


def _invert_kml_coords(coord_text: str) -> tuple[float, float] | None:
  parts = [p.strip() for p in coord_text.strip().split(",")]
  if len(parts) < 2:
    return None
  try:
    lon = float(parts[0])
    lat = float(parts[1])
    return lat, lon
  except ValueError:
    return None


def _team_from_name(name: str) -> str | None:
  n = name.lower()
  if "сбг" in n:
    return "B"
  if "лк" in n:
    return "A"
  return None


def _classify_task_common(name: str) -> tuple[str | None, str | None, str | None]:
  """КТ и ориентиры — общая логика для файлов Задача1 / Задача2."""
  if KT_POINT_PATTERN.search(name.strip()):
    return "point", None, None

  team = _team_from_name(name)
  if team is None:
    return None, None, None

  n = name.lower()
  has_base = "база" in n
  has_start = "старт" in n

  if has_base and has_start:
    return "landmark", "base_start", team
  if has_base:
    return "landmark", "base", team
  if has_start:
    return "landmark", "start", team
  return None, None, None


def _classify_task1(name: str) -> tuple[str | None, str | None, str | None]:
  return _classify_task_common(name)


def _classify_task3(name: str) -> tuple[str | None, str | None, str | None]:
  """Этап 3: посты → точки (штурм ЛК), мертвяки → схроны, базы → landmarks."""
  team = _team_from_name(name)
  n = name.lower()

  if "база" in n and team:
    return "landmark", "base", team
  if POST_PATTERN.search(name.strip()):
    return "point", None, None
  if MERTVYAK_PATTERN.search(name):
    side = team or ("A" if "лк" in n else "B" if "сбг" in n else None)
    return "cache", "mertvyak", side
  return None, None, None


def _classify(name: str, source_name: str) -> tuple[str | None, str | None, str | None]:
  """object_type, cache_kind|landmark_kind, team_side."""
  src = source_name or ""

  if TASK1_FILE_HINT.search(src):
    return _classify_task1(name)

  if TASK2_FILE_HINT.search(src):
    if LANDMARK_EXCLUDE_IN_CACHE_FILES.search(name):
      return None, None, None
    if FILM_LOOT_PATTERN.search(name) or CACHE_PATTERN.search(name) or CACHE_OBJECT_PATTERN.search(name):
      return "cache", "film_loot", None
    return None, None, None

  if TASK3_FILE_HINT.search(src) or (
    LK_FILE_HINT.search(src) and not TASK1_FILE_HINT.search(src) and not TASK2_FILE_HINT.search(src)
  ):
    return _classify_task3(name)

  if SBG_FILE_HINT.search(src) and TASK3_FILE_HINT.search(src):
    return _classify_task3(name)

  if SBG_FILE_HINT.search(src) and not TASK1_FILE_HINT.search(src):
    if LANDMARK_EXCLUDE_IN_CACHE_FILES.search(name):
      return None, None, None
    if CACHE_OBJECT_PATTERN.search(name):
      return "cache", "post", "B"
    return None, None, None

  if LANDMARK_EXCLUDE_IN_CACHE_FILES.search(name):
    return None, None, None
  if POINT_PATTERN.search(name) or KT_POINT_PATTERN.search(name):
    return "point", None, None
  if CACHE_PATTERN.search(name) or CACHE_OBJECT_PATTERN.search(name):
    return "cache", "post", None
  return None, None, None


def parse_kml_bytes(
  kml_bytes: bytes, source_name: str = ""
) -> tuple[list[ParsedPoint], list[ParsedCache], list[ParsedLandmark]]:
  points: list[ParsedPoint] = []
  caches: list[ParsedCache] = []
  landmarks: list[ParsedLandmark] = []
  root = ET.fromstring(kml_bytes)

  for placemark in _placemarks(root):
    name_el = _find(placemark, "name")
    name = (name_el.text or "").strip() if name_el is not None and name_el.text else "Без имени"

    coord_el = _find_coordinates(placemark)
    if coord_el is None or not (coord_el.text and coord_el.text.strip()):
      continue

    first_coord = coord_el.text.strip().split()[0]
    coords = _invert_kml_coords(first_coord)
    if coords is None:
      continue
    lat, lon = coords

    obj_type, sub_kind, team_side = _classify(name, source_name)
    if obj_type == "point":
      stage = 3 if POST_PATTERN.search(name.strip()) else 1
      points.append(ParsedPoint(name=name, lat=lat, lon=lon, stage=stage))
    elif obj_type == "cache":
      kind = sub_kind if sub_kind in ("film_loot", "post", "mertvyak") else "post"
      stage = 2 if kind == "film_loot" else 3
      caches.append(
        ParsedCache(
          name=name,
          lat=lat,
          lon=lon,
          team_side=team_side,
          cache_kind=kind,
          stage=stage,
          loot_variant=loot_variant_from_name(name) if kind == "film_loot" else "film_passage",
        )
      )
    elif obj_type == "landmark" and sub_kind and team_side:
      landmarks.append(
        ParsedLandmark(name=name, lat=lat, lon=lon, kind=sub_kind, team_side=team_side)
      )

  return points, caches, landmarks


def parse_kml_file(path: Path) -> tuple[list[ParsedPoint], list[ParsedCache], list[ParsedLandmark]]:
  return parse_kml_bytes(path.read_bytes(), source_name=path.name)


def parse_kmz_file(
  file_bytes: bytes, source_name: str = ""
) -> tuple[list[ParsedPoint], list[ParsedCache], list[ParsedLandmark]]:
  all_points: list[ParsedPoint] = []
  all_caches: list[ParsedCache] = []
  all_landmarks: list[ParsedLandmark] = []

  with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
    for name in zf.namelist():
      if name.lower().endswith(".kml"):
        pts, cchs, lms = parse_kml_bytes(zf.read(name), source_name=source_name or name)
        all_points.extend(pts)
        all_caches.extend(cchs)
        all_landmarks.extend(lms)

  return all_points, all_caches, all_landmarks


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  """Грубая дистанция для слияния меток на одной точке."""
  from math import cos, radians, sqrt

  dlat = (lat2 - lat1) * 111_320
  dlon = (lon2 - lon1) * 111_320 * cos(radians((lat1 + lat2) / 2))
  return sqrt(dlat * dlat + dlon * dlon)


def merge_landmarks(landmarks: list[ParsedLandmark], threshold_m: float = 25) -> list[ParsedLandmark]:
  """База и старт одной стороны в одной точке → одна метка base_start."""
  result: list[ParsedLandmark] = []
  used: set[int] = set()

  for i, lm in enumerate(landmarks):
    if i in used:
      continue
    if lm.kind == "base":
      for j, other in enumerate(landmarks):
        if j in used or i == j:
          continue
        if other.team_side == lm.team_side and other.kind == "start":
          if _distance_m(lm.lat, lm.lon, other.lat, other.lon) <= threshold_m:
            result.append(
              ParsedLandmark(
                name=f"{lm.name} · {other.name}",
                lat=lm.lat,
                lon=lm.lon,
                kind="base_start",
                team_side=lm.team_side,
              )
            )
            used.add(i)
            used.add(j)
            break
    if i not in used:
      result.append(lm)
      used.add(i)

  return result


def _dedupe_landmarks(landmarks: list[ParsedLandmark], threshold_m: float = 30) -> list[ParsedLandmark]:
  """Сливаем базы/старты одной стороны, если в разных KML чуть разъехались координаты."""
  priority = {"base_start": 3, "base": 2, "start": 1}
  result: list[ParsedLandmark] = []

  for lm in landmarks:
    match_idx: int | None = None
    for i, existing in enumerate(result):
      if existing.team_side != lm.team_side:
        continue
      if _distance_m(existing.lat, existing.lon, lm.lat, lm.lon) > threshold_m:
        continue
      match_idx = i
      break

    if match_idx is None:
      result.append(lm)
      continue

    existing = result[match_idx]
    if priority.get(lm.kind, 0) > priority.get(existing.kind, 0):
      result[match_idx] = lm
    elif priority.get(lm.kind, 0) == priority.get(existing.kind, 0) and len(lm.name) > len(existing.name):
      result[match_idx] = lm

  return result


def _dedupe_places(
  points: list[ParsedPoint],
  caches: list[ParsedCache],
  landmarks: list[ParsedLandmark],
) -> tuple[list[ParsedPoint], list[ParsedCache], list[ParsedLandmark]]:
  """Убираем дубли постов/мертвяков из двух файлов Задача-3."""
  seen_pts: set[tuple[str, float, float]] = set()
  seen_post_coords: list[tuple[float, float]] = []
  out_pts: list[ParsedPoint] = []
  for p in points:
    if p.stage == 3 and POST_PATTERN.search(p.name.strip()):
      if any(_distance_m(p.lat, p.lon, lat, lon) <= 15 for lat, lon in seen_post_coords):
        continue
      seen_post_coords.append((p.lat, p.lon))
    key = (p.name.lower(), round(p.lat, 5), round(p.lon, 5))
    if key in seen_pts:
      continue
    seen_pts.add(key)
    out_pts.append(p)

  seen_c: set[tuple[str, float, float]] = set()
  out_c: list[ParsedCache] = []
  for c in caches:
    key = (c.name.lower(), round(c.lat, 5), round(c.lon, 5))
    if key in seen_c:
      continue
    seen_c.add(key)
    out_c.append(c)

  seen_lm: set[tuple[str, float, float]] = set()
  out_lm: list[ParsedLandmark] = []
  for lm in landmarks:
    key = (lm.name.lower(), round(lm.lat, 5), round(lm.lon, 5))
    if key in seen_lm:
      continue
    seen_lm.add(key)
    out_lm.append(lm)

  out_lm = _dedupe_landmarks(out_lm)
  return out_pts, out_c, out_lm


def load_preset_game_kml(
  kmz_dir: Path,
) -> tuple[list[ParsedPoint], list[ParsedCache], list[ParsedLandmark]]:
  """
  Этап 1: Задача1.kml — КТ + базы/старты
  Этап 2: Задача-2.kml — ящики за плёнкой (лут)
  Этап 3: Задача-3 ЛК + Задача 3-СБГ — посты (точки), мертвяки (схроны); базы только из Задача1
  """
  if not kmz_dir.is_dir():
    return [], [], []

  points: list[ParsedPoint] = []
  caches: list[ParsedCache] = []
  landmarks: list[ParsedLandmark] = []

  task1 = next((p for p in kmz_dir.glob("*.kml") if TASK1_FILE_HINT.search(p.name)), None)
  task2 = next((p for p in kmz_dir.glob("*.kml") if TASK2_FILE_HINT.search(p.name)), None)
  lk = next(
    (p for p in kmz_dir.glob("*.kml") if LK_FILE_HINT.search(p.name) and SBG_FILE_HINT.search(p.name) is None),
    None,
  )
  sbg = next((p for p in kmz_dir.glob("*.kml") if SBG_FILE_HINT.search(p.name)), None)

  if task1:
    pts, _, lms = parse_kml_file(task1)
    points.extend([ParsedPoint(p.name, p.lat, p.lon, stage=1) for p in pts])
    landmarks.extend(merge_landmarks(lms))

  if task2:
    _, c_loot, _ = parse_kml_file(task2)
    caches.extend(
      [
        ParsedCache(c.name, c.lat, c.lon, None, stage=2, cache_kind="film_loot")
        for c in c_loot
      ]
    )

  if lk:
    pts3, c_a, _ = parse_kml_file(lk)
    points.extend([ParsedPoint(p.name, p.lat, p.lon, stage=3) for p in pts3 if p.stage == 3 or POST_PATTERN.search(p.name)])
    points.extend([ParsedPoint(p.name, p.lat, p.lon, stage=1) for p in pts3 if p.stage == 1])
    caches.extend(
      [ParsedCache(c.name, c.lat, c.lon, c.team_side, stage=3, cache_kind=c.cache_kind) for c in c_a]
    )
  if sbg:
    pts3, c_b, _ = parse_kml_file(sbg)
    points.extend([ParsedPoint(p.name, p.lat, p.lon, stage=3) for p in pts3 if POST_PATTERN.search(p.name)])
    caches.extend(
      [ParsedCache(c.name, c.lat, c.lon, c.team_side, stage=3, cache_kind=c.cache_kind) for c in c_b]
    )

  points, caches, landmarks = _dedupe_places(points, caches, landmarks)
  return points, caches, landmarks
