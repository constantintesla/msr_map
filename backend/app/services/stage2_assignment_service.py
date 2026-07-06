import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Cache, GameState, GameStatus, Stage2Assignment
from app.services.game_service import get_or_create_game_state, log_event


def is_stage2_active(game: GameState) -> bool:
  """Ящики доступны при параллельном флаге или при переключении на этап 2."""
  return bool(game.stage2_enabled) or game.current_stage == 2


def get_all_film_loot_ids(db: Session) -> list[int]:
  rows = (
    db.query(Cache.id)
    .filter(Cache.stage == 2, Cache.cache_kind == "film_loot", Cache.enabled.is_(True))
    .order_by(Cache.id)
    .all()
  )
  return [r[0] for r in rows]


def get_active_stage2_cache_id(db: Session) -> int | None:
  """Текущая цель этапа 2 — последняя выдача без доставки на базу."""
  row = (
    db.query(Stage2Assignment.cache_id)
    .join(Cache, Cache.id == Stage2Assignment.cache_id)
    .filter(Cache.delivered_at.is_(None))
    .order_by(Stage2Assignment.round_number.desc())
    .first()
  )
  return row[0] if row else None


def get_active_stage2_cache(db: Session) -> Cache | None:
  cache_id = get_active_stage2_cache_id(db)
  if cache_id is None:
    return None
  return db.query(Cache).filter(Cache.id == cache_id).first()


def get_issued_cache_ids(db: Session) -> set[int]:
  rows = db.query(Stage2Assignment.cache_id).all()
  return {r[0] for r in rows}


def is_cache_issued(db: Session, cache_id: int) -> bool:
  return (
    db.query(Stage2Assignment)
    .filter(Stage2Assignment.cache_id == cache_id)
    .first()
    is not None
  )


def _next_round_number(db: Session) -> int:
  last = db.query(Stage2Assignment).order_by(Stage2Assignment.round_number.desc()).first()
  return (last.round_number if last else 0) + 1


def issue_next_assignment(db: Session) -> Stage2Assignment | None:
  """Выдать следующий невыданный ящик этапа 2."""
  game = get_or_create_game_state(db)
  all_ids = get_all_film_loot_ids(db)
  if not all_ids:
    return None

  issued = get_issued_cache_ids(db)
  remaining = [cid for cid in all_ids if cid not in issued]
  if not remaining:
    return None

  if game.stage2_issue_mode == "sequential":
    idx = game.stage2_sequential_index
    cache_id = None
    for offset in range(len(all_ids)):
      candidate = all_ids[(idx + offset) % len(all_ids)]
      if candidate not in issued:
        cache_id = candidate
        game.stage2_sequential_index = (idx + offset + 1) % len(all_ids)
        break
    if cache_id is None:
      return None
  else:
    cache_id = random.choice(remaining)

  cache = db.query(Cache).filter(Cache.id == cache_id).first()
  now = datetime.utcnow()
  assignment = Stage2Assignment(
    cache_id=cache_id,
    assigned_at=now,
    round_number=_next_round_number(db),
  )
  db.add(assignment)
  game.stage2_last_issued_at = now
  payload = {"cache_id": cache_id, "round": assignment.round_number}
  if cache:
    payload.update(
      {
        "lat": cache.lat,
        "lon": cache.lon,
        "code": cache.detonation_code,
        "name": cache.name,
        "loot_variant": cache.loot_variant or "film_passage",
      }
    )
  log_event(db, "stage2_issued", payload)
  db.commit()
  db.refresh(assignment)
  return assignment


def should_auto_issue(db: Session) -> bool:
  game = get_or_create_game_state(db)
  if game.status != GameStatus.RUNNING.value or not is_stage2_active(game):
    return False
  if game.stage2_last_issued_at is None:
    return True
  elapsed = datetime.utcnow() - game.stage2_last_issued_at
  return elapsed >= timedelta(minutes=game.stage2_issue_interval_minutes)


def maybe_auto_issue(db: Session) -> Stage2Assignment | None:
  if not should_auto_issue(db):
    return None
  issued = get_issued_cache_ids(db)
  all_ids = get_all_film_loot_ids(db)
  if len(issued) >= len(all_ids):
    return None
  return issue_next_assignment(db)


def ensure_initial_assignment(db: Session) -> Stage2Assignment | None:
  """Первая выдача при активации этапа 2, если ещё ничего не выдано."""
  game = get_or_create_game_state(db)
  if not is_stage2_active(game):
    return None
  if get_issued_cache_ids(db):
    return None
  return issue_next_assignment(db)


def stage2_next_issue_at(game: GameState) -> datetime | None:
  if not is_stage2_active(game) or game.status != GameStatus.RUNNING.value:
    return None
  if game.stage2_last_issued_at is None:
    return datetime.utcnow()
  return game.stage2_last_issued_at + timedelta(minutes=game.stage2_issue_interval_minutes)


def enable_stage2_now(db: Session) -> GameState:
  game = get_or_create_game_state(db)
  if not game.stage2_enabled:
    game.stage2_enabled = True
    log_event(db, "stage2_enabled", {"manual": True})
    db.commit()
    db.refresh(game)
  return game


def reset_stage2_assignments(db: Session) -> None:
  game = get_or_create_game_state(db)
  db.query(Stage2Assignment).delete()
  game.stage2_last_issued_at = None
  game.stage2_sequential_index = 0
  game.stage2_enabled = False
