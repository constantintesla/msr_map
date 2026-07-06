from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_commander
from app.database import get_db
from app.lpd_channels import LPD_CHANNELS, lpd_frequency_mhz, lpd_label
from app.models import FieldOrder, User
from app.routers import ws
from app.schemas import (
  CommanderFeedResponse,
  CommanderStatusResponse,
  EngineerChannelUpdate,
  EngineerPoolItem,
  FieldOrderCreate,
  FieldOrderOut,
  LpdChannelOut,
  Stage2ActiveLootOut,
)
from app.services.engineer_pool_service import engineer_password_hint
from app.services.feed_service import build_commander_feed
from app.services.field_order_service import create_field_order, field_order_ws_packet, order_to_out
from app.qr_tokens import ensure_cache_qr_token, ensure_point_qr_token, qr_entry_url
from app.services.game_service import get_or_create_game_state
from app.services.hold_service import refresh_active_hold_progress
from app.services.stage2_assignment_service import get_active_stage2_cache, is_stage2_active
from app.services.status_service import build_status_response

router = APIRouter(prefix="/api/commander", tags=["commander"])


@router.get("/status", response_model=CommanderStatusResponse)
async def commander_status(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
):
  """Карта и объекты текущего этапа для командования стороны."""
  for packet in refresh_active_hold_progress(db):
    await ws.broadcast_hold_update(packet)
  base = build_status_response(
    db,
    stage2_player_view=True,
    viewer_side=user.side,
    viewer_role=user.role,
  )
  active_loot = None
  if is_stage2_active(get_or_create_game_state(db)):
    cache = get_active_stage2_cache(db)
    if cache:
      token = ensure_cache_qr_token(cache, db)
      db.commit()
      active_loot = Stage2ActiveLootOut(
        cache_id=cache.id,
        name=cache.name,
        lat=cache.lat,
        lon=cache.lon,
        code=cache.detonation_code,
        loot_variant=cache.loot_variant or "film_passage",
        url=qr_entry_url(token),
      )
  return CommanderStatusResponse(
    **base.model_dump(),
    viewer_side=user.side or "A",
    side_label="ЛК" if user.side == "A" else "СБГ",
    stage2_active_loot=active_loot,
  )


@router.get("/feed", response_model=CommanderFeedResponse)
def commander_feed(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
):
  """Лента событий игры и сообщений штаба для своей стороны."""
  side = user.side or "A"
  return CommanderFeedResponse(items=build_commander_feed(db, side))


@router.get("/lpd-channels", response_model=list[LpdChannelOut])
def commander_lpd_channels(
  _: Annotated[User, Depends(require_commander)],
):
  return [LpdChannelOut(channel=c.channel, frequency_mhz=c.frequency_mhz) for c in LPD_CHANNELS]


@router.get("/engineers", response_model=list[EngineerPoolItem])
def commander_engineers(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
):
  side = user.side or "A"
  prefix = "eng_a" if side == "A" else "eng_b"
  rows = (
    db.query(User)
    .filter(User.role == "engineer", User.side == side, User.username.like(f"{prefix}%"))
    .order_by(User.username)
    .all()
  )
  return [
    EngineerPoolItem(
      id=u.id,
      username=u.username,
      side=side,
      password_hint=engineer_password_hint(u),
      lpd_channel=u.lpd_channel,
      lpd_frequency_mhz=lpd_frequency_mhz(u.lpd_channel),
      lpd_label=lpd_label(u.lpd_channel),
    )
    for u in rows
  ]


@router.patch("/engineers/{engineer_id}/lpd-channel", response_model=EngineerPoolItem)
async def commander_assign_lpd_channel(
  engineer_id: int,
  body: EngineerChannelUpdate,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
):
  eng = db.query(User).filter(User.id == engineer_id, User.role == "engineer").first()
  if eng is None or eng.side != user.side:
    raise HTTPException(status_code=404, detail="Инженер не найден")
  if body.lpd_channel is not None and body.lpd_channel not in range(1, 70):
    raise HTTPException(status_code=400, detail="Канал LPD должен быть 1–69")

  eng.lpd_channel = body.lpd_channel
  db.commit()
  db.refresh(eng)

  await ws.broadcast_engineer_event(
    eng.side or "A",
    {
      "e": "lpd_channel",
      "u": eng.username,
      "ch": eng.lpd_channel,
      "freq": lpd_frequency_mhz(eng.lpd_channel),
      "label": lpd_label(eng.lpd_channel),
    },
  )

  side = eng.side or "A"
  return EngineerPoolItem(
    id=eng.id,
    username=eng.username,
    side=side,
    password_hint=engineer_password_hint(eng),
    lpd_channel=eng.lpd_channel,
    lpd_frequency_mhz=lpd_frequency_mhz(eng.lpd_channel),
    lpd_label=lpd_label(eng.lpd_channel),
  )


@router.post("/orders", response_model=FieldOrderOut)
async def commander_send_order(
  body: FieldOrderCreate,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
):
  try:
    order = create_field_order(
      db,
      commander=user,
      engineer_user_id=body.engineer_user_id,
      target_kind=body.target_kind,
      target_id=body.target_id,
      note=body.note,
    )
    db.commit()
    db.refresh(order)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  payload = order_to_out(order)
  await ws.broadcast_engineer_event(
    order.side,
    {"e": "field_order", "u": order.engineer_username, "order_id": order.id},
  )
  await ws.broadcast_field_order_update(field_order_ws_packet(order), order.side)
  return FieldOrderOut(**payload)


@router.get("/orders", response_model=list[FieldOrderOut])
def commander_list_orders(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_commander)],
  limit: int = 30,
):
  side = user.side or "A"
  rows = (
    db.query(FieldOrder)
    .filter(FieldOrder.side == side)
    .order_by(FieldOrder.created_at.desc())
    .limit(min(limit, 100))
    .all()
  )
  return [FieldOrderOut(**order_to_out(r)) for r in rows]
