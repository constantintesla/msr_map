from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ChatMessage, User
from app.routers import ws
from app.schemas import ChatMessageOut, ChatMessagesResponse, ChatRecipientOut
from app.services.chat_media import resolve_media_path, save_chat_media
from app.services.scenario_service import get_active_scenario_id

router = APIRouter(prefix="/api/chat", tags=["chat"])

VALID_THREADS = frozenset({"cmd", "eng"})


def _require_chat_user(user: Annotated[User, Depends(get_current_user)]) -> User:
  if user.role not in ("admin", "commander", "engineer"):
    raise HTTPException(status_code=403, detail="Нет доступа к чату")
  return user


def _resolve_side(user: User, side: str | None) -> str:
  if user.role in ("commander", "engineer"):
    if not user.side:
      raise HTTPException(status_code=403, detail="У учётки нет стороны")
    return user.side
  if side not in ("A", "B"):
    raise HTTPException(status_code=400, detail="Укажите сторону A или B")
  return side


def _resolve_thread(
  user: User,
  thread: str | None,
  *,
  for_read: bool = False,
  recipient: str | None = None,
) -> str:
  if user.role == "commander":
    if for_read and thread in VALID_THREADS:
      return thread
    if recipient:
      return "eng"
    return "cmd"
  if user.role == "engineer":
    return "eng"
  if thread not in VALID_THREADS:
    raise HTTPException(status_code=400, detail="Укажите thread: cmd или eng")
  return thread


def _can_access_message(user: User, msg: ChatMessage) -> bool:
  if user.role == "admin":
    return True
  if user.side != msg.side:
    return False
  if user.role == "commander":
    return msg.thread in ("cmd", "eng")
  if user.role == "engineer":
    if msg.thread != "eng":
      return False
    if msg.recipient_username:
      return msg.recipient_username == user.username or msg.sender_username == user.username
    return True
  return False


def _apply_message_visibility(q, user: User, channel_thread: str):
  if user.role != "engineer":
    return q
  return q.filter(
    or_(
      ChatMessage.recipient_username.is_(None),
      ChatMessage.recipient_username == user.username,
      ChatMessage.sender_username == user.username,
    )
  )


def _validate_recipient(db: Session, channel: str, recipient: str | None, user: User, channel_thread: str) -> None:
  if not recipient:
    return
  if user.role not in ("admin", "commander"):
    raise HTTPException(status_code=403, detail="Личные ответы только от штаба или командования")
  if channel_thread != "eng":
    raise HTTPException(status_code=400, detail="Личный ответ только в канале инженеров")
  eng = (
    db.query(User)
    .filter(User.username == recipient, User.role == "engineer", User.side == channel)
    .first()
  )
  if eng is None:
    raise HTTPException(status_code=400, detail="Инженер не найден на этой стороне")


def _to_out(msg: ChatMessage) -> ChatMessageOut:
  return ChatMessageOut(
    id=msg.id,
    created_at=msg.created_at,
    side=msg.side,
    thread=msg.thread or "cmd",
    sender_role=msg.sender_role,
    sender_name=msg.sender_username,
    text=msg.text,
    media_type=msg.media_type,
    has_media=bool(msg.media_path),
    media_filename=msg.media_filename,
    recipient_username=msg.recipient_username,
  )


@router.get("/recipients", response_model=list[ChatRecipientOut])
def chat_recipients(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(_require_chat_user)],
  side: str | None = None,
):
  """Список инженеров стороны для личного ответа в чате."""
  if user.role not in ("admin", "commander"):
    raise HTTPException(status_code=403, detail="Недоступно")
  channel = _resolve_side(user, side)
  rows = (
    db.query(User)
    .filter(User.role == "engineer", User.side == channel)
    .order_by(User.username)
    .all()
  )
  return [ChatRecipientOut(username=u.username) for u in rows]


@router.get("/messages", response_model=ChatMessagesResponse)
def get_chat_messages(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(_require_chat_user)],
  side: str | None = None,
  thread: str | None = None,
  after_id: int = 0,
):
  channel = _resolve_side(user, side)
  channel_thread = _resolve_thread(user, thread, for_read=True)
  q = db.query(ChatMessage).filter(
    ChatMessage.scenario_id == get_active_scenario_id(db),
    ChatMessage.side == channel,
    ChatMessage.thread == channel_thread,
  )
  q = _apply_message_visibility(q, user, channel_thread)
  if after_id > 0:
    q = q.filter(ChatMessage.id > after_id)
    items = q.order_by(ChatMessage.id.asc()).all()
    return ChatMessagesResponse(side=channel, thread=channel_thread, items=[_to_out(m) for m in items])

  items = list(reversed(q.order_by(ChatMessage.id.desc()).limit(80).all()))
  return ChatMessagesResponse(side=channel, thread=channel_thread, items=[_to_out(m) for m in items])


@router.post("/messages", response_model=ChatMessageOut)
async def post_chat_message(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(_require_chat_user)],
  side: Annotated[str | None, Form()] = None,
  thread: Annotated[str | None, Form()] = None,
  recipient_username: Annotated[str | None, Form()] = None,
  text: Annotated[str, Form()] = "",
  file: UploadFile | None = File(None),
):
  channel = _resolve_side(user, side)
  recipient = (recipient_username or "").strip() or None
  channel_thread = _resolve_thread(user, thread, for_read=False, recipient=recipient)
  _validate_recipient(db, channel, recipient, user, channel_thread)
  body = (text or "").strip()

  if not body and (file is None or not file.filename):
    raise HTTPException(status_code=400, detail="Введите текст или прикрепите фото/видео")

  media_type = None
  media_path = None
  media_filename = None
  if file and file.filename:
    media_type, media_path, media_filename = await save_chat_media(file)

  msg = ChatMessage(
    scenario_id=get_active_scenario_id(db),
    side=channel,
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

  await ws.broadcast_chat_event(
    {
      "e": "chat",
      "t": channel,
      "thread": channel_thread,
      "p_id": msg.id,
      "u": user.username,
      "r": user.role,
      "to": recipient,
    }
  )
  return _to_out(msg)


@router.get("/media/{message_id}")
def get_chat_media(
  message_id: int,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(_require_chat_user)],
):
  msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
  if msg is None or not msg.media_path:
    raise HTTPException(status_code=404, detail="Медиа не найдено")
  if not _can_access_message(user, msg):
    raise HTTPException(status_code=403, detail="Нет доступа")

  path = resolve_media_path(msg.media_path)
  return FileResponse(path, filename=msg.media_filename or path.name)
