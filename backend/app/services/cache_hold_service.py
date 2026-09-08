from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Cache, CacheHoldSession
from app.services.capture_settings import post_hold_ping_seconds, post_hold_seconds
from app.services.game_service import get_or_create_game_state, log_event, assert_game_running


def get_active_cache_hold(db: Session, cache_id: int) -> CacheHoldSession | None:
  return (
    db.query(CacheHoldSession)
    .filter(CacheHoldSession.cache_id == cache_id, CacheHoldSession.active.is_(True))
    .first()
  )


def hold_elapsed_seconds(session: CacheHoldSession, now: datetime | None = None) -> int:
  now = now or datetime.utcnow()
  return int((now - session.started_at).total_seconds())


def cache_hold_deadman_seconds(db: Session) -> int:
  return post_hold_ping_seconds(get_or_create_game_state(db))


def cache_hold_required_seconds(db: Session) -> int:
  return post_hold_seconds(get_or_create_game_state(db))


def confirm_cache_hold(db: Session, cache_id: int, side: str) -> CacheHoldSession:
  now = datetime.utcnow()
  cache = db.query(Cache).filter(Cache.id == cache_id).first()
  if cache is None:
    raise ValueError("Схрон не найден")
  if not cache.enabled:
    raise ValueError("Схрон отключён администратором")
  if cache.cache_kind != "post" or cache.stage != 3:
    raise ValueError("Удержание только для схронов этапа 3")
  if cache.destroyed:
    raise ValueError("Схрон уже подорван")
  if cache.team_side and cache.team_side != side:
    raise ValueError("Этот схрон принадлежит другой стороне")

  game = get_or_create_game_state(db)
  assert_game_running(db)
  if game.current_stage != 3:
    raise ValueError(f"Удержание схронов доступно на этапе 3, сейчас этап {game.current_stage}")

  required = post_hold_seconds(game)
  session = get_active_cache_hold(db, cache_id)
  if session is None:
    session = CacheHoldSession(
      scenario_id=cache.scenario_id,
      cache_id=cache_id,
      side=side,
      started_at=now,
      last_ping_at=now,
      active=True,
      hold_ready=False,
    )
    db.add(session)
    try:
      log_event(db, "cache_hold_start", {"cache_id": cache_id, "side": side})
    except IntegrityError:
      # Гонка: параллельный запрос уже создал активную сессию на этот схрон.
      db.rollback()
      session = get_active_cache_hold(db, cache_id)
      if session is None:
        raise
      if session.side != side:
        raise ValueError("Схрон удерживается другой стороной")
      session.last_ping_at = now
      if not session.hold_ready and hold_elapsed_seconds(session, now) >= required:
        session.hold_ready = True
        log_event(db, "cache_hold_ready", {"cache_id": cache_id, "side": side})
      else:
        log_event(db, "cache_hold_ping", {"cache_id": cache_id, "side": side})
  else:
    if session.side != side:
      raise ValueError("Схрон удерживается другой стороной")
    session.last_ping_at = now
    if not session.hold_ready and hold_elapsed_seconds(session, now) >= required:
      session.hold_ready = True
      log_event(db, "cache_hold_ready", {"cache_id": cache_id, "side": side})
    else:
      log_event(db, "cache_hold_ping", {"cache_id": cache_id, "side": side})

  db.commit()
  db.refresh(session)
  return session


def leave_cache_hold(db: Session, cache_id: int, side: str) -> CacheHoldSession | None:
  session = get_active_cache_hold(db, cache_id)
  if session is None or session.side != side:
    return None

  now = datetime.utcnow()
  session.active = False
  session.ended_at = now
  session.hold_ready = False

  log_event(db, "cache_hold_leave", {"cache_id": cache_id, "side": side})
  db.commit()
  db.refresh(session)
  return session


def force_release_cache_hold(db: Session, cache_id: int) -> CacheHoldSession | None:
  session = get_active_cache_hold(db, cache_id)
  if session is None:
    return None
  return leave_cache_hold(db, cache_id, session.side)


def close_expired_cache_holds(db: Session) -> list[CacheHoldSession]:
  from app.services.scenario_service import get_active_scenario_id

  dm = cache_hold_deadman_seconds(db)
  deadline = datetime.utcnow() - timedelta(seconds=dm)
  expired = (
    db.query(CacheHoldSession)
    .filter(
      CacheHoldSession.scenario_id == get_active_scenario_id(db),
      CacheHoldSession.active.is_(True),
      CacheHoldSession.last_ping_at < deadline,
    )
    .all()
  )

  closed: list[CacheHoldSession] = []
  for session in expired:
    result = leave_cache_hold(db, session.cache_id, session.side)
    if result:
      log_event(db, "cache_hold_expired", {"cache_id": session.cache_id, "side": session.side})
      closed.append(result)

  return closed


def require_hold_ready_for_detonation(db: Session, cache_id: int, side: str) -> None:
  session = get_active_cache_hold(db, cache_id)
  required = cache_hold_required_seconds(db)
  ping = cache_hold_deadman_seconds(db)
  if session is None or session.side != side:
    raise ValueError(f"Сначала удерживайте схрон {required // 60} мин (ping каждые {ping // 60} мин)")
  if not session.hold_ready:
    left = required - hold_elapsed_seconds(session)
    raise ValueError(f"До детонации осталось {max(0, left // 60)} мин")
