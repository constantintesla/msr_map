"""EventLog для Башни — со своим явным scenario_id, а не «текущим активным».

Башня не обязана быть активным сценарием движка (регистрация по ссылкам и
игровые действия должны работать независимо от того, что сейчас включено в
`Scenario.is_active`), поэтому не переиспользуем `game_service.log_event`,
который жёстко берёт `get_active_scenario_id(db)`.
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import EventLog


def tower_log_event(db: Session, scenario_id: int, event_type: str, payload: dict | None = None) -> EventLog:
  entry = EventLog(
    scenario_id=scenario_id,
    event_type=event_type,
    payload=json.dumps(payload or {}, ensure_ascii=False),
    created_at=datetime.utcnow(),
  )
  db.add(entry)
  db.flush()
  return entry
