import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EventLog, GameState, GameStatus


def get_or_create_game_state(db: Session) -> GameState:
  state = db.query(GameState).filter(GameState.id == 1).first()
  if state is None:
    state = GameState(id=1, status=GameStatus.IDLE.value)
    db.add(state)
    db.commit()
    db.refresh(state)
  return state


def log_event(db: Session, event_type: str, payload: dict | None = None) -> EventLog:
  entry = EventLog(
    event_type=event_type,
    payload=json.dumps(payload or {}, ensure_ascii=False),
    created_at=datetime.utcnow(),
  )
  db.add(entry)
  db.commit()
  db.refresh(entry)
  return entry
