from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.lpd_channels import lpd_label
from app.models import Cache, EngineerLocation, GameStatus, MovementTrackPoint, Point, User
from app.services.game_service import get_or_create_game_state
from app.routers import ws
from app.schemas import EngineerLocationOut, LocationPingRequest

router = APIRouter(prefix="/api/location", tags=["location"])

STALE_SECONDS = 300  # не показывать на карте старше 5 мин


def _engineer_label(user: User, db: Session) -> str:
  if user.lpd_channel:
    ch = lpd_label(user.lpd_channel)
    if ch:
      return f"{user.username} · {ch}"
  if user.point_id:
    p = db.query(Point).filter(Point.id == user.point_id).first()
    if p:
      return f"{user.username} · {p.name}"
  if user.cache_id:
    c = db.query(Cache).filter(Cache.id == user.cache_id).first()
    if c:
      return f"{user.username} · {c.name}"
  return user.username


@router.post("/ping")
async def location_ping(
  body: LocationPingRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(get_current_user)],
):
  """Инженер отправляет GPS с телефона."""
  if user.role != "engineer":
    raise HTTPException(status_code=403, detail="Только для инженеров")
  if not user.side:
    raise HTTPException(status_code=400, detail="У учётки нет стороны")

  label = _engineer_label(user, db)
  row = db.query(EngineerLocation).filter(EngineerLocation.user_id == user.id).first()
  now = datetime.utcnow()
  if row is None:
    row = EngineerLocation(
      user_id=user.id,
      username=user.username,
      side=user.side,
      label=label,
      lat=body.lat,
      lon=body.lon,
      accuracy=body.accuracy,
      updated_at=now,
    )
    db.add(row)
  else:
    row.username = user.username
    row.side = user.side
    row.label = label
    row.lat = body.lat
    row.lon = body.lon
    row.accuracy = body.accuracy
    row.updated_at = now

  game = get_or_create_game_state(db)
  if game.started_at and game.status in (GameStatus.RUNNING.value, GameStatus.PAUSED.value):
    db.add(
      MovementTrackPoint(
        scenario_id=game.id,
        game_session_id=game.game_session_id or 1,
        user_id=user.id,
        username=user.username,
        side=user.side,
        label=label,
        lat=body.lat,
        lon=body.lon,
        accuracy=body.accuracy,
        recorded_at=now,
      )
    )

  db.commit()
  await ws.broadcast_admin_event({"e": "location", "t": user.side, "u": user.username})
  await ws.broadcast_location_event(user.side, {"e": "location", "t": user.side, "u": user.username})
  return {"ok": True}


@router.get("/engineers", response_model=list[EngineerLocationOut])
def list_engineer_locations(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(get_current_user)],
  side: str | None = None,
):
  """Позиции инженеров для штаба и командования."""
  if user.role not in ("admin", "commander"):
    raise HTTPException(status_code=403, detail="Нет доступа")

  filter_side = user.side if user.role == "commander" else side
  if user.role == "admin" and filter_side not in (None, "A", "B"):
    raise HTTPException(status_code=400, detail="side должен быть A или B")

  cutoff = datetime.utcnow() - timedelta(seconds=STALE_SECONDS)
  q = db.query(EngineerLocation).filter(EngineerLocation.updated_at >= cutoff)
  if filter_side in ("A", "B"):
    q = q.filter(EngineerLocation.side == filter_side)

  items = q.order_by(EngineerLocation.username).all()
  return [
    EngineerLocationOut(
      user_id=r.user_id,
      username=r.username,
      side=r.side,
      label=r.label,
      lat=r.lat,
      lon=r.lon,
      accuracy=r.accuracy,
      updated_at=r.updated_at,
    )
    for r in items
  ]
