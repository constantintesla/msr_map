from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_engineer
from app.database import get_db
from app.models import Cache, User
from app.routers import ws
from app.routers.cache import _check_geofence
from app.schemas import CacheHoldConfirmRequest, CacheHoldLeaveRequest, HoldConfirmRequest, HoldLeaveRequest
from app.services.cache_hold_service import confirm_cache_hold, leave_cache_hold
from app.services.hold_service import (
  confirm_hold,
  expire_hold_if_deadman_elapsed,
  get_active_hold,
  hold_deadman_seconds_for_point,
  hold_elapsed_seconds,
  leave_hold,
  maybe_complete_hold,
)
from app.services.game_service import get_or_create_game_state
from app.models import Point

router = APIRouter(prefix="/api/hold", tags=["hold"])


def _require_side(user: User, side: str) -> None:
  if user.side and user.side != side:
    raise HTTPException(status_code=403, detail="Сторона не совпадает с учётной записью")


async def _broadcast_hold_packets(packets: list[dict]) -> None:
  for packet in packets:
    await ws.broadcast_hold_update(packet)


@router.get("/point/{point_id}")
async def hold_point_state(
  point_id: int,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(get_current_user)],
):
  """Проверка dead-man при входе на страницу удержания."""
  packets: list[dict] = []
  point = db.query(Point).filter(Point.id == point_id).first()
  session = get_active_hold(db, point_id)
  if session and point:
    game = get_or_create_game_state(db)
    event_type = maybe_complete_hold(db, point, session, game)
    if event_type:
      db.commit()
      db.refresh(session)
      packets.append({"e": event_type, "p_id": point_id, "t": session.side})

  expired = expire_hold_if_deadman_elapsed(db, point_id)
  if expired is not None and expired.active is False:
    packets.append({"e": "hold_expired", "p_id": point_id, "t": expired.side})

  await _broadcast_hold_packets(packets)

  session = get_active_hold(db, point_id)
  dm = hold_deadman_seconds_for_point(db, point_id)
  if session is None:
    return {
      "ok": True,
      "active": False,
      "hold_deadman_seconds": dm,
    }
  return {
    "ok": True,
    "active": True,
    "side": session.side,
    "user_id": session.user_id,
    "last_ping_at": session.last_ping_at,
    "hold_ready": session.hold_ready,
    "hold_elapsed_sec": hold_elapsed_seconds(session),
    "hold_deadman_seconds": dm,
  }


@router.post("/confirm")
async def hold_confirm(
  body: HoldConfirmRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  _require_side(user, body.side)
  prev = get_active_hold(db, body.point_id)
  was_ready = bool(prev and prev.hold_ready)
  try:
    session, created = confirm_hold(db, body.point_id, body.side, user.id)
  except ValueError as exc:
    expire_hold_if_deadman_elapsed(db, body.point_id)
    detail = str(exc)
    if detail == "Сторона СБГ обороняется — действия в приложении не требуются":
      raise HTTPException(status_code=403, detail=detail) from exc
    raise HTTPException(status_code=400, detail=detail) from exc

  expire_hold_if_deadman_elapsed(db, body.point_id)
  dm = hold_deadman_seconds_for_point(db, body.point_id)
  packets: list[dict] = []
  if created:
    packets.append({"e": "hold_start", "p_id": body.point_id, "t": body.side})
  else:
    packets.append({"e": "hold_ping", "p_id": body.point_id, "t": body.side})
  if session.hold_ready and not was_ready:
    point = db.query(Point).filter(Point.id == body.point_id).first()
    if point and point.stage == 1:
      packets.append({"e": "point_capture", "p_id": body.point_id, "t": body.side})
    elif point and point.stage == 3:
      packets.append({"e": "point_hold_ready", "p_id": body.point_id, "t": body.side})
  await _broadcast_hold_packets(packets)
  return {
    "ok": True,
    "session_id": session.id,
    "last_ping_at": session.last_ping_at,
    "hold_ready": session.hold_ready,
    "hold_elapsed_sec": hold_elapsed_seconds(session),
    "hold_deadman_seconds": dm,
  }


@router.post("/leave")
async def hold_leave(
  body: HoldLeaveRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  _require_side(user, body.side)
  session = leave_hold(db, body.point_id, body.side, user.id)
  if session is None:
    raise HTTPException(status_code=404, detail="Активное удержание не найдено")
  await ws.broadcast_hold_update({"e": "hold_leave", "p_id": body.point_id, "t": body.side})
  return {"ok": True, "ended_at": session.ended_at}


@router.post("/cache/confirm")
def cache_hold_confirm(
  body: CacheHoldConfirmRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  _require_side(user, body.side)
  cache = db.query(Cache).filter(Cache.id == body.cache_id).first()
  if cache is None:
    raise HTTPException(status_code=404, detail="Объект не найден")
  game = get_or_create_game_state(db)
  _check_geofence(game, cache, body.lat, body.lon, body.accuracy)
  try:
    session = confirm_cache_hold(db, body.cache_id, body.side)
    from app.services.cache_hold_service import hold_elapsed_seconds as cache_hold_elapsed

    return {
      "ok": True,
      "session_id": session.id,
      "last_ping_at": session.last_ping_at,
      "hold_ready": session.hold_ready,
      "hold_elapsed_sec": cache_hold_elapsed(session),
    }
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cache/leave")
def cache_hold_leave(
  body: CacheHoldLeaveRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  _require_side(user, body.side)
  session = leave_cache_hold(db, body.cache_id, body.side)
  if session is None:
    raise HTTPException(status_code=404, detail="Активное удержание не найдено")
  return {"ok": True, "ended_at": session.ended_at}
