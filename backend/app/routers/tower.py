from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import require_tower_commander, require_tower_user
from app.database import get_db
from app.models import User
from app.routers import ws
from app.services.chat_media import resolve_media_path, save_chat_media
from app.tower import commander_service
from app.tower.models import Faction, UrPoint
from app.tower.scan_service import perform_scan
from app.tower.schemas import (
  TowerChatMessageOut,
  TowerChatMessagesResponse,
  TowerChatRecipientOut,
  TowerLocationOut,
  TowerLocationPingRequest,
  TowerOrderCreate,
  TowerOrderDismissResponse,
  TowerOrderOut,
  TowerScanRequest,
  TowerScanResponse,
)
from app.tower.ur_service import refresh_all_zones

router = APIRouter(prefix="/api/tower", tags=["tower"])


@router.post("/scan", response_model=TowerScanResponse)
def scan(
  body: TowerScanRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  if not body.token and not body.code:
    raise HTTPException(status_code=400, detail="Нужен QR-токен или код таблички")
  try:
    kind, data = perform_scan(db, scanner=user, token=body.token, code=body.code)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  return TowerScanResponse(kind=kind, data=data)


@router.get("/status")
def status(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  from app.tower.config_service import current_phase_name, get_tower_config
  from app.tower.scan_service import zone_to_dict

  scenario_id = _user_scenario_id(db, user)
  zones = refresh_all_zones(db, scenario_id)
  cfg = get_tower_config(db, scenario_id)
  return {
    "ur_zones": [zone_to_dict(db, z) for z in zones],
    "current_phase": current_phase_name(cfg),
  }


@router.get("/scannable")
def scannable(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  """Для тестирования до печати QR-табличек: те же цели, что и физические
  таблички, с ручным кодом — чтобы можно было «сканировать» кликом по карте."""
  scanner = db.query(Faction).filter(Faction.id == user.faction_id).first()
  if scanner is None:
    raise HTTPException(status_code=400, detail="У аккаунта нет стороны")

  items: list[dict] = []
  if scanner.kind == "village":
    others = (
      db.query(Faction)
      .filter(Faction.scenario_id == scanner.scenario_id, Faction.kind == "village", Faction.id != scanner.id)
      .all()
    )
    for f in others:
      if f.lat is not None and f.lon is not None:
        items.append({"name": f"Деревня {f.name}", "lat": f.lat, "lon": f.lon, "code": f.manual_code})
  else:
    villages = db.query(Faction).filter(
      Faction.scenario_id == scanner.scenario_id, Faction.kind == "village"
    ).all()
    for f in villages:
      if f.lat is not None and f.lon is not None:
        items.append({"name": f"Деревня {f.name}", "lat": f.lat, "lon": f.lon, "code": f.manual_code})
    points = db.query(UrPoint).filter(UrPoint.scenario_id == scanner.scenario_id).all()
    for p in points:
      items.append({"name": p.name, "lat": p.lat, "lon": p.lon, "code": p.manual_code})

  return {"items": items}


def _user_scenario_id(db: Session, user: User) -> int:
  scenario_id = db.query(Faction.scenario_id).filter(Faction.id == user.faction_id).scalar()
  if scenario_id is None:
    raise HTTPException(status_code=400, detail="У аккаунта нет стороны")
  return scenario_id


# --- чат ---


def _chat_to_out(msg) -> TowerChatMessageOut:
  return TowerChatMessageOut(
    id=msg.id,
    created_at=msg.created_at,
    faction_id=msg.faction_id,
    thread=msg.thread or "cmd",
    sender_role=msg.sender_role,
    sender_name=msg.sender_username,
    text=msg.text,
    media_type=msg.media_type,
    has_media=bool(msg.media_path),
    media_filename=msg.media_filename,
    recipient_username=msg.recipient_username,
  )


@router.get("/chat/recipients", response_model=list[TowerChatRecipientOut])
def chat_recipients(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_commander)],
):
  return [TowerChatRecipientOut(username=u.username) for u in commander_service.list_chat_recipients(db, user)]


@router.get("/chat/messages", response_model=TowerChatMessagesResponse)
def chat_messages(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
  thread: str | None = None,
  after_id: int = 0,
):
  channel_thread, items = commander_service.list_chat_messages(db, user=user, thread=thread, after_id=after_id)
  return TowerChatMessagesResponse(
    faction_id=user.faction_id, thread=channel_thread, items=[_chat_to_out(m) for m in items]
  )


@router.post("/chat/messages", response_model=TowerChatMessageOut)
async def post_chat_message(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
  thread: Annotated[str | None, Form()] = None,
  recipient_username: Annotated[str | None, Form()] = None,
  text: Annotated[str, Form()] = "",
  file: UploadFile | None = File(None),
):
  media_type = media_path = media_filename = None
  if file and file.filename:
    media_type, media_path, media_filename = await save_chat_media(file)

  try:
    msg = commander_service.post_chat_message(
      db,
      user=user,
      thread=thread,
      recipient_username=recipient_username,
      text=text,
      media_type=media_type,
      media_path=media_path,
      media_filename=media_filename,
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  await ws.broadcast_tower_chat_event(
    user.faction_id,
    {"e": "tower_chat", "thread": msg.thread, "p_id": msg.id, "u": user.username, "r": user.role},
  )
  return _chat_to_out(msg)


@router.get("/chat/media/{message_id}")
def chat_media(
  message_id: int,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  from app.models import ChatMessage

  msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
  if msg is None or not msg.media_path:
    raise HTTPException(status_code=404, detail="Медиа не найдено")
  if not commander_service.can_access_message(user, msg):
    raise HTTPException(status_code=403, detail="Нет доступа")
  path = resolve_media_path(msg.media_path)
  return FileResponse(path, filename=msg.media_filename or path.name)


# --- приказы ---


@router.post("/orders", response_model=TowerOrderOut)
async def create_order(
  body: TowerOrderCreate,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_commander)],
):
  try:
    order = commander_service.create_field_order(
      db,
      commander=user,
      target_username=body.target_username,
      target_name=body.target_name,
      target_lat=body.target_lat,
      target_lon=body.target_lon,
      note=body.note,
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  payload = commander_service.order_to_out(order)
  await ws.broadcast_tower_order_update(
    user.faction_id, {"e": "tower_order", "order_id": order.id, "u": order.engineer_username}
  )
  return TowerOrderOut(**payload)


@router.get("/orders", response_model=list[TowerOrderOut])
def list_orders(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_commander)],
  limit: int = 30,
):
  rows = commander_service.list_orders_for_commander(db, user, limit=limit)
  return [TowerOrderOut(**commander_service.order_to_out(r)) for r in rows]


@router.get("/orders/active", response_model=list[TowerOrderOut])
def active_orders(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  rows = commander_service.list_active_orders_for_user(db, user)
  return [TowerOrderOut(**commander_service.order_to_out(r)) for r in rows]


@router.post("/orders/{order_id}/dismiss", response_model=TowerOrderDismissResponse)
async def dismiss_order(
  order_id: int,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  try:
    order = commander_service.dismiss_order(db, user, order_id)
  except ValueError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
  await ws.broadcast_tower_order_update(
    order.faction_id, {"e": "tower_order_update", "order_id": order.id, "ack": True}
  )
  return TowerOrderDismissResponse(ok=True, order=TowerOrderOut(**commander_service.order_to_out(order)))


# --- геолокация ---


@router.post("/location/ping")
async def location_ping(
  body: TowerLocationPingRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_user)],
):
  commander_service.ping_location(db, user, body.lat, body.lon, body.accuracy)
  await ws.broadcast_tower_location_event(
    user.faction_id, {"e": "tower_location", "u": user.username}
  )
  return {"ok": True}


@router.get("/location/roster", response_model=list[TowerLocationOut])
def location_roster(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_tower_commander)],
):
  rows = commander_service.list_roster(db, user.faction_id)
  return [
    TowerLocationOut(
      user_id=r.user_id,
      username=r.username,
      faction_id=r.faction_id,
      lat=r.lat,
      lon=r.lon,
      accuracy=r.accuracy,
      updated_at=r.updated_at,
    )
    for r in rows
  ]
