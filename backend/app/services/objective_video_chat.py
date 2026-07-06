from sqlalchemy.orm import Session

from app.models import ChatMessage, User
from app.routers import ws


def side_label(side: str) -> str:
  return "ЛК" if side == "A" else "СБГ"


async def publish_objective_video_chat(
  db: Session,
  *,
  user: User,
  side: str,
  text: str,
  media_type: str,
  media_path: str,
  media_filename: str,
) -> ChatMessage:
  msg = ChatMessage(
    side=side,
    thread="cmd",
    sender_role=user.role,
    sender_username=user.username,
    text=text,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )
  db.add(msg)
  db.flush()
  await ws.broadcast_chat_event(
    {
      "e": "chat",
      "t": side,
      "thread": "cmd",
      "p_id": msg.id,
      "u": user.username,
      "r": user.role,
    }
  )
  return msg
