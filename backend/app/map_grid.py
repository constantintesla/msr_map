"""Загрузка буквенно-цифровой сетки из map.kmz (GroundOverlay + grid_overlay.png)."""

from __future__ import annotations

import os
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.kmz_parser import KML_NS, KML_URI

MAP_KMZ_NAME = "map.kmz"
MAP_KML_NAME = "map.kml"
GRID_IMAGE_NAME = "grid_overlay.png"


@dataclass(frozen=True)
class MapGridOverlay:
  north: float
  south: float
  east: float
  west: float


def _find_tag(parent: ET.Element, tag: str) -> ET.Element | None:
  for candidate in (
    parent.find(f"kml:{tag}", KML_NS),
    parent.find(f"{{{KML_URI}}}{tag}"),
    parent.find(tag),
  ):
    if candidate is not None:
      return candidate
  return None


def _find_all(parent: ET.Element, tag: str) -> list[ET.Element]:
  items = parent.findall(f".//{{{KML_URI}}}{tag}")
  if not items:
    items = parent.findall(f".//kml:{tag}", KML_NS)
  if not items:
    items = parent.findall(f".//{tag}")
  return list(items)


def _parse_float(text: str | None) -> float | None:
  if text is None:
    return None
  try:
    return float(text.strip())
  except ValueError:
    return None


def parse_ground_overlay_from_kml(kml_bytes: bytes) -> MapGridOverlay | None:
  root = ET.fromstring(kml_bytes)
  for overlay in _find_all(root, "GroundOverlay"):
    box = _find_tag(overlay, "LatLonBox")
    if box is None:
      continue
    north = _parse_float(_find_tag(box, "north").text if _find_tag(box, "north") is not None else None)
    south = _parse_float(_find_tag(box, "south").text if _find_tag(box, "south") is not None else None)
    east = _parse_float(_find_tag(box, "east").text if _find_tag(box, "east") is not None else None)
    west = _parse_float(_find_tag(box, "west").text if _find_tag(box, "west") is not None else None)
    if None in (north, south, east, west):
      continue
    return MapGridOverlay(north=north, south=south, east=east, west=west)
  return None


def default_kmz_dir() -> Path:
  """
  Локально: msr_map/kmz (рядом с backend/).
  В Docker: /app/kmz (volume, часто read-only).
  """
  backend_root = Path(__file__).resolve().parents[1]
  container_kmz = backend_root / "kmz"
  if container_kmz.is_dir():
    return container_kmz
  return backend_root.parent / "kmz"


def _grid_cache_dir() -> Path:
  cache = Path(__file__).resolve().parents[1] / ".grid_cache"
  cache.mkdir(parents=True, exist_ok=True)
  return cache


def _overlay_from_kmz(kmz_path: Path) -> MapGridOverlay | None:
  with zipfile.ZipFile(kmz_path) as zf:
    kml_name = next((n for n in zf.namelist() if n.lower().endswith(".kml")), None)
    if kml_name is None:
      return None
    return parse_ground_overlay_from_kml(zf.read(kml_name))


def _extract_grid_image(zf: zipfile.ZipFile, out_dir: Path) -> Path | None:
  image_name = next((n for n in zf.namelist() if n.replace("\\", "/").endswith(GRID_IMAGE_NAME)), None)
  if image_name is None:
    return None
  out_dir.mkdir(parents=True, exist_ok=True)
  out_path = out_dir / GRID_IMAGE_NAME
  out_path.write_bytes(zf.read(image_name))
  return out_path


def _resolve_grid_image(kmz_path: Path, preferred_dir: Path) -> Path | None:
  """PNG из kmz/ (если уже есть) или извлечение в writable-каталог."""
  local_png = preferred_dir / GRID_IMAGE_NAME
  if local_png.is_file():
    return local_png

  cache_png = _grid_cache_dir() / GRID_IMAGE_NAME
  try:
    kmz_mtime = kmz_path.stat().st_mtime
    if cache_png.is_file() and cache_png.stat().st_mtime >= kmz_mtime:
      return cache_png
  except OSError:
    pass

  targets: list[Path] = []
  if os.access(preferred_dir, os.W_OK):
    targets.append(preferred_dir)
  targets.append(_grid_cache_dir())

  with zipfile.ZipFile(kmz_path) as zf:
    for target in targets:
      extracted = _extract_grid_image(zf, target)
      if extracted is not None:
        return extracted
  return None


def ensure_map_grid_assets(kmz_dir: Path | None = None) -> tuple[MapGridOverlay | None, Path | None]:
  """
  Возвращает границы сетки и путь к PNG.
  В проде kmz/ смонтирован read-only — PNG кэшируется в backend/.grid_cache/.
  """
  base = kmz_dir or default_kmz_dir()
  kmz_path = base / MAP_KMZ_NAME
  image_path = base / GRID_IMAGE_NAME

  if kmz_path.is_file():
    overlay = _overlay_from_kmz(kmz_path)
    if overlay is not None:
      png = _resolve_grid_image(kmz_path, base)
      if png is not None:
        return overlay, png

  kml_path = base / MAP_KML_NAME
  if kml_path.is_file() and image_path.is_file():
    overlay = parse_ground_overlay_from_kml(kml_path.read_bytes())
    if overlay is not None:
      return overlay, image_path

  return None, None
