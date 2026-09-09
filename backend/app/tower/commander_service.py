"""Командирская консоль Башни: чат, приказы, геолокация — сгруппировано по
faction_id вместо side (см. app/routers/chat.py, location.py,
services/field_order_service.py — тот же функционал, старые side-таблицы
переиспользуются, но группировка своя, т.к. side: String(1) на Postgres
не вмещает коды факций)."""

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ChatMessage, EngineerLocation, FieldOrder, User
from app.tower.models import Faction

VALID_THREADS = frozenset({"cmd", "eng"})

# side: String(1) NOT NULL в старых A/B-таблицах (chat_messages/field_orders/
# engineer_locations) — переиспользуем эти таблицы для Башни, но группируем
# по faction_id, а не по side. "T" — заглушка, чтобы не нарушать NOT NULL;
# ни один существующий A/B-запрос её не увидит, т.к. они всегда фильтруют
# по своему scenario_id (Башня живёт в отдельном Scenario).
TOWER_SIDE_PLACEHOLDER = "T"


def _faction_scenario_id(db: Session, faction_id: int | None) -> int:
  """Scenario_id стороны Башни — не «активный» сценарий движка (см.
  app/tower/scan_service.py: Башня должна работать независимо от общего
  переключателя сценариев, в том числе до его активации)."""
  scenario_id = db.query(Faction.scenario_id).filter(Faction.id == faction_id).scalar()
  if scenario_id is None:
    raise ValueError("У аккаунта нет стороны")
  return scenario_id


# --- чат ---


def resolve_thread(user: User, thread: str | None, *, recipient: str | None = None) -> str:
  """Явно переданный thread — приоритет (и на чтение, и на запись); иначе
  DM-получатель подразумевает eng, а без того и другого — cmd (штаб)."""
  if user.role == "commander":
    if thread in VALID_THREADS:
      return thread
    return "eng" if recipient else "cmd"
  return "eng"


def can_access_message(user: User, msg: ChatMessage) -> bool:
  if msg.faction_id != user.faction_id:
    return False
  if user.role == "commander":
    return msg.thread in VALID_THREADS
  if msg.thread != "eng":
    return False
  if msg.recipient_username:
    return msg.recipient_username == user.username or msg.sender_username == user.username
  return True


def list_chat_messages(
  db: Session, *, user: User, thread: str | None, after_id: int = 0
) -> tuple[str, list[ChatMessage]]:
  channel_thread = resolve_thread(user, thread)
  q = db.query(ChatMessage).filter(
    ChatMessage.scenario_id == _faction_scenario_id(db, user.faction_id),
    ChatMessage.faction_id == user.faction_id,
    ChatMessage.thread == channel_thread,
  )
  if user.role != "commander":
    q = q.filter(
      or_(
        ChatMessage.recipient_username.is_(None),
        ChatMessage.recipient_username == user.username,
        ChatMessage.sender_username == user.username,
      )
    )
  if after_id > 0:
    items = q.filter(ChatMessage.id > after_id).order_by(ChatMessage.id.asc()).all()
  else:
    items = list(reversed(q.order_by(ChatMessage.id.desc()).limit(80).all()))
  return channel_thread, items


def post_chat_message(
  db: Session,
  *,
  user: User,
  thread: str | None,
  recipient_username: str | None,
  text: str,
  media_type: str | None = None,
  media_path: str | None = None,
  media_filename: str | None = None,
) -> ChatMessage:
  recipient = (recipient_username or "").strip() or None
  channel_thread = resolve_thread(user, thread, recipient=recipient)
  if recipient:
    if user.role != "commander":
      raise ValueError("Личные ответы только от командования")
    if channel_thread != "eng":
      raise ValueError("Личный ответ только в канале своих игроков")
    target = (
      db.query(User)
      .filter(User.username == recipient, User.faction_id == user.faction_id)
      .first()
    )
    if target is None:
      raise ValueError("Игрок не найден в вашей стороне")

  body = (text or "").strip()
  if not body and not media_path:
    raise ValueError("Введите текст или прикрепите фото/видео")

  msg = ChatMessage(
    scenario_id=_faction_scenario_id(db, user.faction_id),
    side=TOWER_SIDE_PLACEHOLDER,
    faction_id=user.faction_id,
    thread=channel_thread,
    sender_role=user.role,
    sender_username=user.username,
    text=body or None,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
    recipient_username=recipient,
  )
  db.add(msg)
  db.commit()
  db.refresh(msg)
  return msg


def list_chat_recipients(db: Session, user: User) -> list[User]:
  return (
    db.query(User)
    .filter(User.faction_id == user.faction_id, User.role == "faction")
    .order_by(User.username)
    .all()
  )


# --- приказы ---


def dismiss_active_orders(db: Session, engineer_user_id: int, scenario_id: int) -> None:
  now = datetime.utcnow()
  rows = (
    db.query(FieldOrder)
    .filter(
      FieldOrder.scenario_id == scenario_id,
      FieldOrder.engineer_user_id == engineer_user_id,
      FieldOrder.dismissed_at.is_(None),
    )
    .all()
  )
  for row in rows:
    row.dismissed_at = now


def create_field_order(
  db: Session,
  *,
  commander: User,
  target_username: str,
  target_name: str,
  target_lat: float,
  target_lon: float,
  note: str | None,
) -> FieldOrder:
  target_user = (
    db.query(User)
    .filter(User.username == target_username, User.faction_id == commander.faction_id)
    .first()
  )
  if target_user is None:
    raise ValueError("Игрок не найден в вашей стороне")

  scenario_id = _faction_scenario_id(db, commander.faction_id)
  dismiss_active_orders(db, target_user.id, scenario_id)

  order = FieldOrder(
    scenario_id=scenario_id,
    side=TOWER_SIDE_PLACEHOLDER,
    faction_id=commander.faction_id,
    commander_username=commander.username,
    engineer_user_id=target_user.id,
    engineer_username=target_user.username,
    target_kind="custom",
    target_id=0,
    target_name=target_name,
    target_lat=target_lat,
    target_lon=target_lon,
    note=(note or "").strip() or None,
  )
  db.add(order)
  db.flush()
  db.commit()
  db.refresh(order)
  return order


def list_orders_for_commander(db: Session, commander: User, limit: int = 30) -> list[FieldOrder]:
  return (
    db.query(FieldOrder)
    .filter(
      FieldOrder.scenario_id == _faction_scenario_id(db, commander.faction_id),
      FieldOrder.faction_id == commander.faction_id,
    )
    .order_by(FieldOrder.created_at.desc())
    .limit(min(limit, 100))
    .all()
  )


def list_active_orders_for_user(db: Session, user: User) -> list[FieldOrder]:
  return (
    db.query(FieldOrder)
    .filter(
      FieldOrder.scenario_id == _faction_scenario_id(db, user.faction_id),
      FieldOrder.engineer_user_id == user.id,
      FieldOrder.dismissed_at.is_(None),
    )
    .order_by(FieldOrder.created_at.desc())
    .limit(5)
    .all()
  )


def dismiss_order(db: Session, user: User, order_id: int) -> FieldOrder:
  order = (
    db.query(FieldOrder)
    .filter(FieldOrder.id == order_id, FieldOrder.engineer_user_id == user.id)
    .first()
  )
  if order is None:
    raise ValueError("Приказ не найден")
  if order.dismissed_at is None:
    order.dismissed_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
  return order


def order_to_out(order: FieldOrder) -> dict:
  return {
    "id": order.id,
    "created_at": order.created_at,
    "faction_id": order.faction_id,
    "commander_username": order.commander_username,
    "target_username": order.engineer_username,
    "target_name": order.target_name,
    "target_lat": order.target_lat,
    "target_lon": order.target_lon,
    "note": order.note,
    "dismissed": order.dismissed_at is not None,
  }


# --- геолокация ---


def ping_location(db: Session, user: User, lat: float, lon: float, accuracy: float) -> EngineerLocation:
  now = datetime.utcnow()
  row = db.query(EngineerLocation).filter(EngineerLocation.user_id == user.id).first()
  if row is None:
    row = EngineerLocation(
      user_id=user.id,
      scenario_id=_faction_scenario_id(db, user.faction_id),
      username=user.username,
      side=TOWER_SIDE_PLACEHOLDER,
      faction_id=user.faction_id,
      label=user.username,
      lat=lat,
      lon=lon,
      accuracy=accuracy,
      updated_at=now,
    )
    db.add(row)
  else:
    row.scenario_id = _faction_scenario_id(db, user.faction_id)
    row.username = user.username
    row.faction_id = user.faction_id
    row.label = user.username
    row.lat = lat
    row.lon = lon
    row.accuracy = accuracy
    row.updated_at = now
  db.commit()
  db.refresh(row)
  return row


STALE_SECONDS = 300


def list_roster_for_scenario(db: Session, scenario_id: int) -> list[EngineerLocation]:
  """Все стороны сразу — для админа (в отличие от list_roster, которая
  всегда одна конкретная сторона командира)."""
  from datetime import timedelta

  cutoff = datetime.utcnow() - timedelta(seconds=STALE_SECONDS)
  return (
    db.query(EngineerLocation)
    .filter(EngineerLocation.scenario_id == scenario_id, EngineerLocation.updated_at >= cutoff)
    .order_by(EngineerLocation.username)
    .all()
  )


def list_roster(db: Session, faction_id: int) -> list[EngineerLocation]:
  from datetime import timedelta

  cutoff = datetime.utcnow() - timedelta(seconds=STALE_SECONDS)
  return (
    db.query(EngineerLocation)
    .filter(
      EngineerLocation.faction_id == faction_id,
      EngineerLocation.scenario_id == _faction_scenario_id(db, faction_id),
      EngineerLocation.updated_at >= cutoff,
    )
    .order_by(EngineerLocation.username)
    .all()
  )
