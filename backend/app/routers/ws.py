import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User

router = APIRouter(tags=["websocket"])

# Подключённые админ-клиенты для broadcast событий
admin_connections: set[WebSocket] = set()
commander_connections: dict[str, set[WebSocket]] = {"A": set(), "B": set()}
engineer_connections: dict[str, set[WebSocket]] = {"A": set(), "B": set()}

# Башня: произвольное число сторон, ключ — faction_id (не "A"/"B")
tower_connections: dict[int, set[WebSocket]] = {}


def _authenticate_user(token: str | None, roles: set[str]) -> User | None:
  if not token:
    return None
  try:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    username = payload.get("sub")
    if not username:
      return None
    db = SessionLocal()
    try:
      user = db.query(User).filter(User.username == username).first()
      if user is None or user.role not in roles:
        return None
      return user
    finally:
      db.close()
  except JWTError:
    return None


def _authenticate_ws(token: str | None) -> bool:
  return _authenticate_user(token, {"admin"}) is not None


async def broadcast_admin_event(packet: dict) -> None:
  """Рассылка микро-пакетов всем подключённым админам."""
  dead: list[WebSocket] = []
  message = json.dumps(packet, ensure_ascii=False)
  for ws in admin_connections:
    try:
      await ws.send_text(message)
    except Exception:
      dead.append(ws)
  for ws in dead:
    admin_connections.discard(ws)


async def broadcast_chat_event(packet: dict) -> None:
  """Новое сообщение чата — админам и участникам канала (cmd/eng)."""
  await broadcast_admin_event(packet)
  side = packet.get("t")
  if side not in ("A", "B"):
    return
  thread = packet.get("thread", "cmd")
  message = json.dumps(packet, ensure_ascii=False)
  dead: list[WebSocket] = []

  pools: list[set[WebSocket]] = []
  if thread == "cmd":
    pools.append(commander_connections.get(side, set()))
  else:
    pools.append(engineer_connections.get(side, set()))
    pools.append(commander_connections.get(side, set()))

  for pool in pools:
    for ws in pool:
      try:
        await ws.send_text(message)
      except Exception:
        dead.append(ws)
  for ws in dead:
    admin_connections.discard(ws)
    for side_key in ("A", "B"):
      commander_connections[side_key].discard(ws)
      engineer_connections[side_key].discard(ws)


async def broadcast_hold_update(packet: dict) -> None:
  """События захвата/удержания — админу и обоим командованиям."""
  await broadcast_admin_event(packet)
  await broadcast_commander_event("A", packet)
  await broadcast_commander_event("B", packet)


async def broadcast_stage2_issued(cache_id: int) -> None:
  """Новая цель этапа 2 — админу, командованиям и инженерам обеих сторон."""
  from app.database import SessionLocal
  from app.models import Cache

  db = SessionLocal()
  try:
    cache = db.query(Cache).filter(Cache.id == cache_id).first()
    extra: dict = {}
    if cache:
      extra = {
        "lat": cache.lat,
        "lon": cache.lon,
        "code": cache.detonation_code,
        "name": cache.name,
        "loot_variant": cache.loot_variant or "film_passage",
      }
  finally:
    db.close()

  packet = {"e": "stage2_issued", "p_id": cache_id, **extra}
  await broadcast_admin_event(packet)
  await broadcast_commander_event("A", packet)
  await broadcast_commander_event("B", packet)
  await broadcast_engineer_event("A", packet)
  await broadcast_engineer_event("B", packet)


async def broadcast_game_state(status: str) -> None:
  """Смена статуса игры (idle / running / paused) — всем клиентам."""
  packet = {"e": "game_state", "t": status}
  await broadcast_admin_event(packet)
  for side in ("A", "B"):
    await broadcast_commander_event(side, packet)
    await broadcast_engineer_event(side, packet)


async def broadcast_scenario_switched(scenario_id: int) -> None:
  """Активный сценарий сменился — клиенты должны полностью перезагрузить статус."""
  packet = {"e": "scenario_switched", "scenario_id": scenario_id}
  await broadcast_admin_event(packet)
  for side in ("A", "B"):
    await broadcast_commander_event(side, packet)
    await broadcast_engineer_event(side, packet)


async def broadcast_settings_update() -> None:
  """Настройки изменены — клиенты обновляют статус."""
  packet = {"e": "settings_update"}
  await broadcast_admin_event(packet)
  for side in ("A", "B"):
    await broadcast_commander_event(side, packet)
    await broadcast_engineer_event(side, packet)


async def broadcast_commander_event(side: str, packet: dict) -> None:
  """События для командования стороны."""
  if side not in ("A", "B"):
    return
  dead: list[WebSocket] = []
  message = json.dumps(packet, ensure_ascii=False)
  for ws in commander_connections.get(side, set()):
    try:
      await ws.send_text(message)
    except Exception:
      dead.append(ws)
  for ws in dead:
    commander_connections[side].discard(ws)


async def broadcast_field_order_update(order_packet: dict, side: str) -> None:
  """Новый приказ или подтверждение — админу, командованию и инженерам стороны."""
  await broadcast_admin_event(order_packet)
  await broadcast_commander_event(side, order_packet)
  await broadcast_engineer_event(side, order_packet)


async def broadcast_location_event(side: str, packet: dict) -> None:
  """Обновление GPS инженера — командованию стороны."""
  if side not in ("A", "B"):
    return
  dead: list[WebSocket] = []
  message = json.dumps(packet, ensure_ascii=False)
  for ws in commander_connections.get(side, set()):
    try:
      await ws.send_text(message)
    except Exception:
      dead.append(ws)
  for ws in dead:
    commander_connections[side].discard(ws)


async def broadcast_engineer_event(side: str, packet: dict) -> None:
  """События для инженеров стороны (канал LPD и т.д.)."""
  if side not in ("A", "B"):
    return
  dead: list[WebSocket] = []
  message = json.dumps(packet, ensure_ascii=False)
  for ws in engineer_connections.get(side, set()):
    try:
      await ws.send_text(message)
    except Exception:
      dead.append(ws)
  for ws in dead:
    engineer_connections[side].discard(ws)


@router.websocket("/ws/admin")
async def ws_admin(websocket: WebSocket, token: str | None = None):
  """
  WebSocket для админ-панели.
  Микро-пакеты: {"e":"ping","p_id":2,"t":"A"} и события игры.
  """
  if not _authenticate_ws(token):
    # Закрываем после accept — иначе браузер видит обрыв до handshake
    await websocket.accept()
    await websocket.close(code=4401, reason="Unauthorized")
    return

  await websocket.accept()
  admin_connections.add(websocket)

  try:
    while True:
      raw = await websocket.receive_text()
      try:
        packet = json.loads(raw)
      except json.JSONDecodeError:
        continue

      # Эхо ping-пакетов для live-карты
      if packet.get("e") == "ping":
        await broadcast_admin_event(packet)
      else:
        await broadcast_admin_event(packet)
  except WebSocketDisconnect:
    pass
  finally:
    admin_connections.discard(websocket)


@router.websocket("/ws/commander")
async def ws_commander(websocket: WebSocket, token: str | None = None):
  """WebSocket для командования: push новых сообщений чата."""
  user = _authenticate_user(token, {"commander"})
  if user is None or not user.side:
    await websocket.accept()
    await websocket.close(code=4401, reason="Unauthorized")
    return

  side = user.side
  await websocket.accept()
  commander_connections[side].add(websocket)

  try:
    while True:
      await websocket.receive_text()
  except WebSocketDisconnect:
    pass
  finally:
    commander_connections[side].discard(websocket)


async def broadcast_tower_event(faction_id: int, packet: dict) -> None:
  """Событие для одной стороны Башни — админам всегда, плюс участникам этой
  стороны (командиру и игрокам вместе — один пул на faction_id; фактический
  доступ к содержимому cmd/eng-тредов чата всё равно проверяется на GET,
  этот пакет — только сигнал «обновись»)."""
  await broadcast_admin_event(packet)
  dead: list[WebSocket] = []
  message = json.dumps(packet, ensure_ascii=False)
  for ws in tower_connections.get(faction_id, set()):
    try:
      await ws.send_text(message)
    except Exception:
      dead.append(ws)
  for ws in dead:
    tower_connections.get(faction_id, set()).discard(ws)


async def broadcast_tower_chat_event(faction_id: int, packet: dict) -> None:
  await broadcast_tower_event(faction_id, packet)


async def broadcast_tower_location_event(faction_id: int, packet: dict) -> None:
  await broadcast_tower_event(faction_id, packet)


async def broadcast_tower_order_update(faction_id: int, packet: dict) -> None:
  await broadcast_tower_event(faction_id, packet)


async def broadcast_tower_ur_update(packet: dict) -> None:
  """Статус УР интересен обеим воюющим за него сторонам (СБГ и ДРГ) — шлём всем
  подключённым Башне разом, это не приватная информация внутри стороны."""
  await broadcast_admin_event(packet)
  dead: list[tuple[int, WebSocket]] = []
  message = json.dumps(packet, ensure_ascii=False)
  for faction_id, pool in tower_connections.items():
    for ws in pool:
      try:
        await ws.send_text(message)
      except Exception:
        dead.append((faction_id, ws))
  for faction_id, ws in dead:
    tower_connections.get(faction_id, set()).discard(ws)


@router.websocket("/ws/tower")
async def ws_tower(websocket: WebSocket, token: str | None = None):
  """WebSocket для сторон Башни (командир и рядовые вместе, один пул на faction_id)."""
  user = _authenticate_user(token, {"commander", "faction"})
  if user is None or not user.faction_id:
    await websocket.accept()
    await websocket.close(code=4401, reason="Unauthorized")
    return

  faction_id = user.faction_id
  await websocket.accept()
  tower_connections.setdefault(faction_id, set()).add(websocket)

  try:
    while True:
      await websocket.receive_text()
  except WebSocketDisconnect:
    pass
  finally:
    tower_connections.get(faction_id, set()).discard(websocket)


@router.websocket("/ws/engineer")
async def ws_engineer(websocket: WebSocket, token: str | None = None):
  """WebSocket для инженеров: push сообщений штаба."""
  user = _authenticate_user(token, {"engineer"})
  if user is None or not user.side:
    await websocket.accept()
    await websocket.close(code=4401, reason="Unauthorized")
    return

  side = user.side
  await websocket.accept()
  engineer_connections[side].add(websocket)

  try:
    while True:
      await websocket.receive_text()
  except WebSocketDisconnect:
    pass
  finally:
    engineer_connections[side].discard(websocket)
