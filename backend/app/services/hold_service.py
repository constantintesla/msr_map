from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GameState, HoldSession, Point
from app.services.capture_settings import point_capture_seconds, point_hold_ping_seconds, post_hold_ping_seconds, post_hold_seconds, stage1_recapturable
from app.services.game_service import get_or_create_game_state, log_event, assert_game_running

HOLD_BUSY_OTHER_SIDE = "Точка уже удерживается другой стороной"
HOLD_BUSY_OTHER_ENGINEER = "Точка уже удерживается другим инженером"
HOLD_ALREADY_CAPTURED = "Точка уже захвачена"
HOLD_ALREADY_CAPTURED_OURS = "Точка уже под контролем вашей стороны"
POST_ALREADY_DESTROYED = "Пост уже подорван"
POST_SBG_PASSIVE = "Сторона СБГ обороняется — действия в приложении не требуются"
POST_ASSAULT_CODE_FIRST = "Сначала введите код и начните штурм"


def is_stage1_captured(point: Point) -> bool:
  return point.stage == 1 and point.side is not None


def assert_can_start_point_hold(point: Point, side: str, game: GameState | None = None) -> None:
  """Запрет повторного захвата своей КТ и вмешательства в чужой захват."""
  if not point.enabled:
    raise ValueError("Точка отключена администратором")
  if is_stage1_captured(point):
    if point.side == side:
      raise ValueError(HOLD_ALREADY_CAPTURED_OURS)
    if game is not None and stage1_recapturable(game):
      return
    raise ValueError(HOLD_ALREADY_CAPTURED)


def hold_elapsed_seconds(session: HoldSession, now: datetime | None = None) -> int:
  now = now or datetime.utcnow()
  return int((now - session.started_at).total_seconds())


def get_active_hold(db: Session, point_id: int) -> HoldSession | None:
  return (
    db.query(HoldSession)
    .filter(HoldSession.point_id == point_id, HoldSession.active.is_(True))
    .first()
  )


def hold_deadman_seconds_for_point(db: Session, point_id: int) -> int:
  from app.services.game_service import get_or_create_game_state

  point = db.query(Point).filter(Point.id == point_id).first()
  game = get_or_create_game_state(db)
  return _hold_deadman_seconds(game, point)


def _hold_deadman_seconds(game: GameState, point: Point | None) -> int:
  if point is not None and point.stage == 1:
    return point_hold_ping_seconds(game)
  if point is not None and point.stage == 3:
    return post_hold_ping_seconds(game)
  return settings.hold_deadman_seconds


def expire_hold_if_deadman_elapsed(db: Session, point_id: int) -> HoldSession | None:
  """Снять удержание, если с последнего ping прошло ≥ hold_deadman_seconds."""
  from app.services.game_service import get_or_create_game_state

  session = get_active_hold(db, point_id)
  if session is None:
    return None
  point = db.query(Point).filter(Point.id == point_id).first()
  if point is None:
    return session
  game = get_or_create_game_state(db)
  if maybe_complete_hold(db, point, session, game):
    db.commit()
    db.refresh(session)
  deadline = session.last_ping_at + timedelta(seconds=_hold_deadman_seconds(game, point))
  if datetime.utcnow() >= deadline:
    return leave_hold(db, point_id, session.side, session.user_id)
  return session


def _hold_required_seconds(game: GameState, point: Point) -> int:
  if point.stage == 1:
    return point_capture_seconds(game)
  if point.stage == 3:
    return post_hold_seconds(game)
  return 0


def maybe_complete_hold(
  db: Session,
  point: Point,
  session: HoldSession,
  game: GameState | None = None,
) -> str | None:
  """Завершить захват/удержание по истечении времени. Возвращает тип события или None."""
  game = game or get_or_create_game_state(db)
  required = _hold_required_seconds(game, point)
  if point.stage not in (1, 3) or session.hold_ready or required <= 0:
    return None

  if hold_elapsed_seconds(session) < required:
    return None

  session.hold_ready = True
  now = datetime.utcnow()
  if point.stage == 1:
    previous_side = point.side
    point.side = session.side
    session.active = False
    session.ended_at = now
    event_type = "point_recapture" if previous_side and previous_side != session.side else "point_capture"
    log_event(db, event_type, {"point_id": point.id, "side": session.side, "previous_side": previous_side})
    return event_type
  log_event(db, "point_hold_ready", {"point_id": point.id, "side": session.side})
  return "point_hold_ready"


def reconcile_stage1_captured_sessions(db: Session, scenario_id: int) -> None:
  """Закрыть зависшие сессии у уже захваченных КТ (после смены логики)."""
  points = (
    db.query(Point)
    .filter(Point.scenario_id == scenario_id, Point.stage == 1, Point.side.isnot(None))
    .all()
  )
  if not points:
    return
  changed = False
  for point in points:
    session = get_active_hold(db, point.id)
    if session is None:
      continue
    session.hold_ready = True
    session.active = False
    session.ended_at = datetime.utcnow()
    changed = True
  if changed:
    db.commit()


def refresh_active_hold_progress(db: Session) -> list[dict]:
  """Проверить все активные удержания и завершить захват по таймеру."""
  game = get_or_create_game_state(db)
  reconcile_stage1_captured_sessions(db, game.id)
  active = (
    db.query(HoldSession)
    .filter(HoldSession.scenario_id == game.id, HoldSession.active.is_(True))
    .all()
  )
  if not active:
    return []

  point_ids = {s.point_id for s in active}
  points = {p.id: p for p in db.query(Point).filter(Point.id.in_(point_ids)).all()}
  events: list[dict] = []
  for session in active:
    point = points.get(session.point_id)
    if point is None:
      continue
    event_type = maybe_complete_hold(db, point, session, game)
    if event_type:
      events.append({"e": event_type, "p_id": point.id, "t": session.side})
  if events:
    db.commit()
  return events


def _advance_hold_progress(
  db: Session,
  point: Point,
  session: HoldSession,
  side: str,
  now: datetime,
  game: GameState,
) -> str | None:
  """Подтверждение ping: проверить прогресс захвата. Возвращает событие завершения или None."""
  event_type = maybe_complete_hold(db, point, session, game)
  if event_type:
    return event_type
  log_event(db, "hold_ping", {"point_id": point.id, "side": side})
  return None


def confirm_hold(
  db: Session,
  point_id: int,
  side: str,
  user_id: int,
  *,
  allow_stage1_start: bool = False,
  allow_stage3_start: bool = False,
) -> tuple[HoldSession, bool]:
  """Подтверждение удержания по кнопке (dead-man ping, 120 сек)."""
  from app.services.game_service import get_or_create_game_state

  now = datetime.utcnow()
  point = db.query(Point).filter(Point.id == point_id).first()
  if point is None:
    raise ValueError("Точка не найдена")

  game = get_or_create_game_state(db)
  assert_game_running(db)
  if point.stage == 1 and game.current_stage == 3:
    raise ValueError("Захват КТ недоступен на этапе штурма постов")
  if point.stage == 3 and game.current_stage != 3:
    raise ValueError("Удержание постов только на этапе 3")
  if point.stage not in (1, 3):
    raise ValueError(f"Точка активна на этапе {point.stage}")
  if point.stage == 3:
    if point.destroyed:
      raise ValueError(POST_ALREADY_DESTROYED)
    if side == "B":
      raise ValueError(POST_SBG_PASSIVE)

  created = False
  session = get_active_hold(db, point_id)
  if session is not None:
    if session.side != side:
      raise ValueError(HOLD_BUSY_OTHER_SIDE)
    if session.user_id is not None and session.user_id != user_id:
      raise ValueError(HOLD_BUSY_OTHER_ENGINEER)
    session.last_ping_at = now
    _advance_hold_progress(db, point, session, side, now, game)
  else:
    assert_can_start_point_hold(point, side, game)
    if point.stage == 1 and not allow_stage1_start:
      raise ValueError("Сначала введите код с таблички и нажмите «Начать захват»")
    if point.stage == 3 and not allow_stage3_start:
      raise ValueError(POST_ASSAULT_CODE_FIRST)
    if point.stage == 1:
      from app.services.stage1_schedule_service import assert_stage1_capturable

      assert_stage1_capturable(point, game)
    session = HoldSession(
      scenario_id=point.scenario_id,
      point_id=point_id,
      side=side,
      user_id=user_id,
      started_at=now,
      last_ping_at=now,
      active=True,
    )
    db.add(session)
    if point.stage == 3:
      point.side = side
    try:
      log_event(db, "hold_start", {"point_id": point_id, "side": side, "user_id": user_id})
      created = True
    except IntegrityError:
      # Гонка: параллельный запрос уже создал активную сессию на эту точку.
      db.rollback()
      session = get_active_hold(db, point_id)
      if session is None:
        raise
      if session.side != side:
        raise ValueError(HOLD_BUSY_OTHER_SIDE)
      if session.user_id is not None and session.user_id != user_id:
        raise ValueError(HOLD_BUSY_OTHER_ENGINEER)
      session.last_ping_at = now
      _advance_hold_progress(db, point, session, side, now, game)

  db.commit()
  db.refresh(session)
  return session, created


def leave_hold(
  db: Session,
  point_id: int,
  side: str,
  user_id: int | None = None,
) -> HoldSession | None:
  """Сброс удержания (вручную или по истечении dead-man)."""
  session = get_active_hold(db, point_id)
  if session is None or session.side != side:
    return None
  if user_id is not None and session.user_id is not None and session.user_id != user_id:
    return None

  session.active = False
  session.ended_at = datetime.utcnow()
  session.hold_ready = False

  point = db.query(Point).filter(Point.id == point_id).first()
  if point:
    if point.stage == 1 and is_stage1_captured(point):
      pass
    elif point.stage != 3:
      point.side = None

  log_event(db, "hold_leave", {"point_id": point_id, "side": side})
  db.commit()
  db.refresh(session)
  return session


def force_release_hold(db: Session, point_id: int) -> HoldSession | None:
  session = get_active_hold(db, point_id)
  if session is None:
    return None
  return leave_hold(db, point_id, session.side)


def close_expired_holds(db: Session) -> list[HoldSession]:
  """Фоновая задача: закрытие hold после истечения dead-man интервала."""
  from app.services.game_service import get_or_create_game_state

  game = get_or_create_game_state(db)
  now = datetime.utcnow()
  active = (
    db.query(HoldSession)
    .filter(HoldSession.scenario_id == game.id, HoldSession.active.is_(True))
    .all()
  )
  point_ids = {s.point_id for s in active}
  points = {p.id: p for p in db.query(Point).filter(Point.id.in_(point_ids)).all()} if point_ids else {}

  closed: list[HoldSession] = []
  for session in active:
    point = points.get(session.point_id)
    if point is not None and maybe_complete_hold(db, point, session, game):
      db.commit()
    dm = _hold_deadman_seconds(game, point)
    if session.last_ping_at >= now - timedelta(seconds=dm):
      continue
    result = leave_hold(db, session.point_id, session.side)
    if result:
      log_event(db, "hold_expired", {"point_id": session.point_id, "side": session.side})
      closed.append(result)

  if closed:
    db.commit()
  return closed


def require_point_hold_ready(db: Session, point_id: int, side: str) -> None:
  session = get_active_hold(db, point_id)
  if session is None or session.side != side:
    raise ValueError("Сначала удерживайте пост 10 минут (ping каждые 2 мин)")
  if not session.hold_ready:
    left = post_hold_seconds(get_or_create_game_state(db)) - hold_elapsed_seconds(session)
    raise ValueError(f"До детонации осталось {max(0, left // 60)} мин")
