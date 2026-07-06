import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EventLog, GameState, GameStatus, Stage2Assignment

GAME_NOT_STARTED = "Игра не запущена. Нажмите «Старт» в админке."
GAME_PAUSED_MSG = "Игра на паузе. Захват временно недоступен."


def get_or_create_game_state(db: Session) -> GameState:
  state = db.query(GameState).filter(GameState.id == 1).first()
  if state is None:
    state = GameState(id=1, status=GameStatus.IDLE.value)
    db.add(state)
    db.commit()
    db.refresh(state)
  return state


def log_event(db: Session, event_type: str, payload: dict | None = None) -> EventLog:
  entry = EventLog(
    event_type=event_type,
    payload=json.dumps(payload or {}, ensure_ascii=False),
    created_at=datetime.utcnow(),
  )
  db.add(entry)
  db.commit()
  db.refresh(entry)
  return entry


def assert_game_running(db: Session) -> GameState:
  """Запрет действий игроков, пока админ не нажал «Старт» или игра на паузе."""
  state = get_or_create_game_state(db)
  if state.status == GameStatus.IDLE.value:
    raise ValueError(GAME_NOT_STARTED)
  if state.status == GameStatus.PAUSED.value:
    raise ValueError(GAME_PAUSED_MSG)
  return state


def start_game(db: Session) -> GameState:
  state = get_or_create_game_state(db)
  if state.status == GameStatus.RUNNING.value:
    return state
  now = datetime.utcnow()
  state.status = GameStatus.RUNNING.value
  if state.started_at is None:
    state.started_at = now
  state.paused_at = None
  log_event(db, "game_start", {})
  db.commit()
  db.refresh(state)
  return state


def pause_game(db: Session) -> GameState:
  state = get_or_create_game_state(db)
  if state.status != GameStatus.RUNNING.value:
    raise ValueError("Пауза доступна только во время активной игры")
  state.status = GameStatus.PAUSED.value
  state.paused_at = datetime.utcnow()
  log_event(db, "game_pause", {})
  db.commit()
  db.refresh(state)
  return state


def reset_game(db: Session) -> GameState:
  from app.models import Cache, CacheHoldSession, HoldSession, Point, PointReconPhoto

  state = get_or_create_game_state(db)
  state.status = GameStatus.IDLE.value
  state.started_at = None
  state.paused_at = None
  state.score_a = 0
  state.score_b = 0
  state.current_stage = 1

  db.query(HoldSession).delete()
  db.query(CacheHoldSession).delete()
  db.query(PointReconPhoto).delete()
  db.query(Stage2Assignment).delete()
  for point in db.query(Point).all():
    point.side = None
    point.destroyed = False
    point.destroyed_at = None
    point.destroyed_by_side = None
    point.admin_confirmed = False
  for cache in db.query(Cache).all():
    cache.destroyed = False
    cache.destroyed_at = None
    cache.destroyed_by_side = None
    cache.delivery_reported_at = None
    cache.delivered_at = None
    cache.delivered_by_side = None
    cache.admin_confirmed = False
    cache.code_verified_at = None
    cache.code_verified_by_side = None
    cache.code_verified_qr_token = None

  state.stage2_last_issued_at = None
  state.stage2_sequential_index = 0
  state.stage2_enabled = False
  state.stage1_current_slot = -1
  state.stage1_slots_started_at = None

  log_event(db, "game_reset", {})
  db.commit()
  db.refresh(state)
  return state


def set_stage(db: Session, stage: int) -> GameState:
  """Переключение этапа: снимает удержания на других этапах."""
  from app.models import CacheHoldSession, HoldSession, Point
  from app.services.cache_hold_service import leave_cache_hold
  from app.services.hold_service import leave_hold

  if stage not in (1, 2, 3):
    raise ValueError("Этап должен быть 1, 2 или 3")

  state = get_or_create_game_state(db)
  state.current_stage = stage
  if stage == 2:
    state.stage2_enabled = True

  active = db.query(HoldSession).filter(HoldSession.active.is_(True)).all()
  point_stages = {p.id: p.stage for p in db.query(Point).all()}
  for session in active:
    if point_stages.get(session.point_id) != stage:
      leave_hold(db, session.point_id, session.side)

  cache_active = db.query(CacheHoldSession).filter(CacheHoldSession.active.is_(True)).all()
  from app.models import Cache

  cache_stages = {c.id: c.stage for c in db.query(Cache).all()}
  for session in cache_active:
    if cache_stages.get(session.cache_id) != stage:
      leave_cache_hold(db, session.cache_id, session.side)

  log_event(db, "stage_change", {"stage": stage})
  db.commit()
  db.refresh(state)
  return state
