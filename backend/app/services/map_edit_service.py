"""CRUD геометрии объектов карты (только при idle), в рамках активного сценария."""

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
  Cache,
  CacheHoldSession,
  FieldOrder,
  GameState,
  GameStatus,
  HoldSession,
  Landmark,
  Point,
  PointReconPhoto,
  Stage2Assignment,
  User,
)
from app.services.game_service import get_or_create_game_state, log_event
from app.services.scenario_service import get_active_scenario_id
from app.services.stage1_schedule_service import kt_number_from_name
from app.qr_tokens import ensure_cache_qr_token, ensure_point_qr_token

MAP_EDIT_NOT_IDLE = "Редактирование карты доступно только до старта игры"

VALID_POINT_STAGES = {1, 3}
VALID_CACHE_KINDS = {"film_loot", "post", "mertvyak"}
VALID_LOOT_VARIANTS = {"film_passage", "box_direct"}
VALID_LANDMARK_KINDS = {"base", "start", "base_start"}
VALID_SIDES = {"A", "B"}

POST_NUMBER_RE = re.compile(r"^пост[-\s]?(\d+)", re.IGNORECASE)


def assert_game_idle(db: Session) -> GameState:
  state = get_or_create_game_state(db)
  if state.status != GameStatus.IDLE.value:
    raise ValueError(MAP_EDIT_NOT_IDLE)
  return state


def _next_id(db: Session, model: type[Point] | type[Cache] | type[Landmark]) -> int:
  return (db.query(func.max(model.id)).scalar() or 0) + 1


def _next_kt_number(db: Session, scenario_id: int) -> int:
  points = db.query(Point).filter(Point.scenario_id == scenario_id, Point.stage == 1).all()
  nums = [n for p in points if (n := kt_number_from_name(p.name)) is not None]
  return max(nums, default=0) + 1


def _next_post_number(db: Session, scenario_id: int) -> int:
  points = db.query(Point).filter(Point.scenario_id == scenario_id, Point.stage == 3).all()
  nums: list[int] = []
  for p in points:
    m = POST_NUMBER_RE.match(p.name.strip())
    if m:
      nums.append(int(m.group(1)))
  return max(nums, default=0) + 1


def _next_film_loot_number(db: Session, scenario_id: int) -> int:
  caches = (
    db.query(Cache)
    .filter(Cache.scenario_id == scenario_id, Cache.stage == 2, Cache.cache_kind == "film_loot")
    .all()
  )
  nums: list[int] = []
  for c in caches:
    m = re.search(r"(\d+)", c.name)
    if m:
      nums.append(int(m.group(1)))
  return max(nums, default=0) + 1


def _next_mertvyak_number(db: Session, scenario_id: int, team_side: str) -> int:
  caches = (
    db.query(Cache)
    .filter(
      Cache.scenario_id == scenario_id,
      Cache.stage == 3,
      Cache.cache_kind == "mertvyak",
      Cache.team_side == team_side,
    )
    .all()
  )
  return len(caches) + 1


def _point_code(point_id: int, stage: int) -> str:
  base = 4000 + point_id if stage == 1 else 3000 + point_id
  return f"{base:04d}"[-4:]


def _cache_code(cache_id: int, cache_kind: str, film_loot_index: int | None = None) -> str:
  if cache_kind == "film_loot":
    idx = film_loot_index or cache_id
    return f"{2000 + idx:04d}"[-4:]
  return f"{1000 + cache_id:04d}"[-4:]


def _assert_no_active_point_hold(db: Session, point_id: int) -> None:
  active = (
    db.query(HoldSession)
    .filter(HoldSession.point_id == point_id, HoldSession.active.is_(True))
    .first()
  )
  if active:
    raise ValueError("Нельзя удалить точку с активным удержанием")


def _assert_no_active_cache_hold(db: Session, cache_id: int) -> None:
  active = (
    db.query(CacheHoldSession)
    .filter(CacheHoldSession.cache_id == cache_id, CacheHoldSession.active.is_(True))
    .first()
  )
  if active:
    raise ValueError("Нельзя удалить объект с активным удержанием")


def create_point(
  db: Session,
  *,
  lat: float,
  lon: float,
  stage: int,
  name: str | None = None,
) -> Point:
  assert_game_idle(db)
  if stage not in VALID_POINT_STAGES:
    raise ValueError("Этап точки должен быть 1 или 3")

  scenario_id = get_active_scenario_id(db)
  point_id = _next_id(db, Point)
  if name is None:
    name = f"КТ{_next_kt_number(db, scenario_id)}" if stage == 1 else f"Пост-{_next_post_number(db, scenario_id)}"

  point = Point(
    id=point_id,
    scenario_id=scenario_id,
    name=name.strip(),
    lat=lat,
    lon=lon,
    stage=stage,
    detonation_code=_point_code(point_id, stage),
  )
  ensure_point_qr_token(point, db)
  db.add(point)
  db.commit()
  db.refresh(point)
  log_event(db, "map_edit", {"action": "create_point", "point_id": point.id, "name": point.name})
  return point


def update_point(
  db: Session,
  point_id: int,
  *,
  lat: float | None = None,
  lon: float | None = None,
  name: str | None = None,
) -> Point:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  point = db.query(Point).filter(Point.id == point_id, Point.scenario_id == scenario_id).first()
  if point is None:
    raise LookupError("Точка не найдена")
  if lat is not None:
    point.lat = lat
  if lon is not None:
    point.lon = lon
  if name is not None:
    point.name = name.strip()
  db.commit()
  db.refresh(point)
  log_event(db, "map_edit", {"action": "update_point", "point_id": point.id})
  return point


def delete_point(db: Session, point_id: int) -> None:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  point = db.query(Point).filter(Point.id == point_id, Point.scenario_id == scenario_id).first()
  if point is None:
    raise LookupError("Точка не найдена")
  _assert_no_active_point_hold(db, point_id)

  db.query(PointReconPhoto).filter(PointReconPhoto.point_id == point_id).delete()
  db.query(HoldSession).filter(HoldSession.point_id == point_id).delete()
  db.query(FieldOrder).filter(FieldOrder.target_kind == "point", FieldOrder.target_id == point_id).delete()
  db.query(User).filter(User.point_id == point_id).update({User.point_id: None})
  db.delete(point)
  db.commit()
  log_event(db, "map_edit", {"action": "delete_point", "point_id": point_id})


def create_cache(
  db: Session,
  *,
  lat: float,
  lon: float,
  stage: int,
  cache_kind: str,
  team_side: str | None = None,
  name: str | None = None,
  loot_variant: str = "film_passage",
) -> Cache:
  assert_game_idle(db)
  if cache_kind not in VALID_CACHE_KINDS:
    raise ValueError("Недопустимый тип схрона")
  if cache_kind == "film_loot" and stage != 2:
    raise ValueError("Ящики создаются только на этапе 2")
  if cache_kind in {"post", "mertvyak"} and stage != 3:
    raise ValueError("Посты и мертвяки создаются только на этапе 3")
  if cache_kind == "mertvyak":
    if team_side not in VALID_SIDES:
      raise ValueError("Для мертвяка укажите сторону A или B")
  else:
    team_side = team_side if team_side in VALID_SIDES else None

  if cache_kind == "film_loot" and loot_variant not in VALID_LOOT_VARIANTS:
    raise ValueError("Тип ящика: film_passage или box_direct")

  scenario_id = get_active_scenario_id(db)
  cache_id = _next_id(db, Cache)
  film_idx: int | None = None
  if name is None:
    if cache_kind == "film_loot":
      film_idx = _next_film_loot_number(db, scenario_id)
      name = f"Ящик {film_idx}"
    elif cache_kind == "mertvyak":
      side_label = "ЛК" if team_side == "A" else "СБГ"
      name = f"Мертвяк {side_label} {_next_mertvyak_number(db, scenario_id, team_side or 'A')}"
    else:
      name = f"Пост-{cache_id}"

  cache = Cache(
    id=cache_id,
    scenario_id=scenario_id,
    name=name.strip(),
    lat=lat,
    lon=lon,
    stage=stage,
    cache_kind=cache_kind,
    team_side=team_side,
    detonation_code=_cache_code(cache_id, cache_kind, film_idx),
    enabled=True,
    loot_variant=loot_variant if cache_kind == "film_loot" else "film_passage",
  )
  ensure_cache_qr_token(cache, db)
  db.add(cache)
  db.commit()
  db.refresh(cache)
  log_event(db, "map_edit", {"action": "create_cache", "cache_id": cache.id, "name": cache.name})
  return cache


def update_cache(
  db: Session,
  cache_id: int,
  *,
  lat: float | None = None,
  lon: float | None = None,
  name: str | None = None,
  team_side: str | None = None,
) -> Cache:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  cache = db.query(Cache).filter(Cache.id == cache_id, Cache.scenario_id == scenario_id).first()
  if cache is None:
    raise LookupError("Схрон не найден")
  if lat is not None:
    cache.lat = lat
  if lon is not None:
    cache.lon = lon
  if name is not None:
    cache.name = name.strip()
  if team_side is not None:
    if team_side not in VALID_SIDES:
      raise ValueError("Сторона должна быть A или B")
    cache.team_side = team_side
  db.commit()
  db.refresh(cache)
  log_event(db, "map_edit", {"action": "update_cache", "cache_id": cache.id})
  return cache


def delete_cache(db: Session, cache_id: int) -> None:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  cache = db.query(Cache).filter(Cache.id == cache_id, Cache.scenario_id == scenario_id).first()
  if cache is None:
    raise LookupError("Схрон не найден")
  _assert_no_active_cache_hold(db, cache_id)

  db.query(CacheHoldSession).filter(CacheHoldSession.cache_id == cache_id).delete()
  db.query(Stage2Assignment).filter(Stage2Assignment.cache_id == cache_id).delete()
  db.query(FieldOrder).filter(FieldOrder.target_kind == "cache", FieldOrder.target_id == cache_id).delete()
  db.query(User).filter(User.cache_id == cache_id).update({User.cache_id: None})
  db.delete(cache)
  db.commit()
  log_event(db, "map_edit", {"action": "delete_cache", "cache_id": cache_id})


def create_landmark(
  db: Session,
  *,
  lat: float,
  lon: float,
  kind: str,
  team_side: str,
  name: str | None = None,
) -> Landmark:
  assert_game_idle(db)
  if kind not in VALID_LANDMARK_KINDS:
    raise ValueError("Недопустимый тип ориентира")
  if team_side not in VALID_SIDES:
    raise ValueError("Сторона должна быть A или B")

  scenario_id = get_active_scenario_id(db)
  landmark_id = _next_id(db, Landmark)
  if name is None:
    side_label = "ЛК" if team_side == "A" else "СБГ"
    kind_label = {"base": "База", "start": "Старт", "base_start": "База + старт"}[kind]
    name = f"{kind_label} {side_label}"

  landmark = Landmark(
    id=landmark_id,
    scenario_id=scenario_id,
    name=name.strip(),
    lat=lat,
    lon=lon,
    kind=kind,
    team_side=team_side,
  )
  db.add(landmark)
  db.commit()
  db.refresh(landmark)
  log_event(db, "map_edit", {"action": "create_landmark", "landmark_id": landmark.id, "name": landmark.name})
  return landmark


def update_landmark(
  db: Session,
  landmark_id: int,
  *,
  lat: float | None = None,
  lon: float | None = None,
  name: str | None = None,
  kind: str | None = None,
  team_side: str | None = None,
) -> Landmark:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  landmark = (
    db.query(Landmark).filter(Landmark.id == landmark_id, Landmark.scenario_id == scenario_id).first()
  )
  if landmark is None:
    raise LookupError("Ориентир не найден")
  if lat is not None:
    landmark.lat = lat
  if lon is not None:
    landmark.lon = lon
  if name is not None:
    landmark.name = name.strip()
  if kind is not None:
    if kind not in VALID_LANDMARK_KINDS:
      raise ValueError("Недопустимый тип ориентира")
    landmark.kind = kind
  if team_side is not None:
    if team_side not in VALID_SIDES:
      raise ValueError("Сторона должна быть A или B")
    landmark.team_side = team_side
  db.commit()
  db.refresh(landmark)
  log_event(db, "map_edit", {"action": "update_landmark", "landmark_id": landmark.id})
  return landmark


def delete_landmark(db: Session, landmark_id: int) -> None:
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)
  landmark = (
    db.query(Landmark).filter(Landmark.id == landmark_id, Landmark.scenario_id == scenario_id).first()
  )
  if landmark is None:
    raise LookupError("Ориентир не найден")
  db.delete(landmark)
  db.commit()
  log_event(db, "map_edit", {"action": "delete_landmark", "landmark_id": landmark_id})


def wipe_all_objects(db: Session) -> tuple[int, int, int]:
  """Полностью удалить все точки, схроны и ориентиры активного сценария (только до старта игры)."""
  assert_game_idle(db)
  scenario_id = get_active_scenario_id(db)

  n_points = db.query(Point).filter(Point.scenario_id == scenario_id).count()
  n_caches = db.query(Cache).filter(Cache.scenario_id == scenario_id).count()
  n_landmarks = db.query(Landmark).filter(Landmark.scenario_id == scenario_id).count()

  point_ids = [p.id for p in db.query(Point.id).filter(Point.scenario_id == scenario_id).all()]
  cache_ids = [c.id for c in db.query(Cache.id).filter(Cache.scenario_id == scenario_id).all()]

  db.query(PointReconPhoto).filter(PointReconPhoto.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(HoldSession).filter(HoldSession.scenario_id == scenario_id).delete(synchronize_session=False)
  db.query(CacheHoldSession).filter(CacheHoldSession.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(Stage2Assignment).filter(Stage2Assignment.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(FieldOrder).filter(
    FieldOrder.scenario_id == scenario_id, FieldOrder.target_kind.in_(("point", "cache"))
  ).delete(synchronize_session=False)
  if point_ids:
    db.query(User).filter(User.point_id.in_(point_ids)).update(
      {User.point_id: None}, synchronize_session=False
    )
  if cache_ids:
    db.query(User).filter(User.cache_id.in_(cache_ids)).update(
      {User.cache_id: None}, synchronize_session=False
    )
  db.query(Point).filter(Point.scenario_id == scenario_id).delete(synchronize_session=False)
  db.query(Cache).filter(Cache.scenario_id == scenario_id).delete(synchronize_session=False)
  db.query(Landmark).filter(Landmark.scenario_id == scenario_id).delete(synchronize_session=False)
  db.commit()

  log_event(
    db,
    "map_edit",
    {
      "action": "wipe_all",
      "points": n_points,
      "caches": n_caches,
      "landmarks": n_landmarks,
    },
  )
  return n_points, n_caches, n_landmarks
