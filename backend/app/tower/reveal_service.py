"""Раскрытие координат схронов деревни по расписанию реального времени.

Универсальный алгоритм: TowerConfig.reveal_schedule_json — отсортированный
список ISO-datetime порогов. Сколько порогов уже наступило — столько целей
по порядку reveal_order раскрыто конкретной наблюдающей стороне. Расписание
можно сделать сколь угодно длинным (например каждые 15 минут) — логика та
же, не завязана на конкретное число схронов или порогов.
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.tower.config_service import get_tower_config
from app.tower.events import tower_log_event
from app.tower.models import Faction, VillageCacheTarget, VillageRevealState


def _reveal_schedule(schedule_json: str | None) -> list[datetime]:
  if not schedule_json:
    return []
  raw = json.loads(schedule_json)
  return sorted(datetime.fromisoformat(x) for x in raw)


def allowed_reveal_count(db: Session, scenario_id: int, now: datetime | None = None) -> int:
  cfg = get_tower_config(db, scenario_id)
  schedule = _reveal_schedule(cfg.reveal_schedule_json)
  now = now or datetime.utcnow()
  return sum(1 for threshold in schedule if threshold <= now)


def scan_village_board(
  db: Session,
  *,
  scenario_id: int,
  viewer: Faction,
  target: Faction,
  now: datetime | None = None,
) -> dict:
  """Сканирование доски (QR) деревни `target` стороной `viewer`."""
  now = now or datetime.utcnow()
  if viewer.id == target.id:
    raise ValueError("Нельзя сканировать табличку собственной деревни")

  result: dict = {
    "kind": "village",
    "target_faction_code": target.code,
    "target_faction_name": target.name,
  }

  if viewer.kind == "village":
    allowed = allowed_reveal_count(db, scenario_id, now)
    state = (
      db.query(VillageRevealState)
      .filter(
        VillageRevealState.scenario_id == scenario_id,
        VillageRevealState.target_faction_id == target.id,
        VillageRevealState.viewer_faction_id == viewer.id,
      )
      .first()
    )
    if state is None:
      state = VillageRevealState(
        scenario_id=scenario_id,
        target_faction_id=target.id,
        viewer_faction_id=viewer.id,
        revealed_count=0,
      )
      db.add(state)
      db.flush()

    if state.revealed_count < allowed:
      state.revealed_count = allowed
      state.last_revealed_at = now
      tower_log_event(
        db,
        scenario_id,
        "tower_village_revealed",
        {"target": target.code, "viewer": viewer.code, "count": state.revealed_count},
      )

    targets = (
      db.query(VillageCacheTarget)
      .filter(VillageCacheTarget.faction_id == target.id)
      .order_by(VillageCacheTarget.reveal_order)
      .all()
    )
    revealed = targets[: state.revealed_count]
    result["cache_targets"] = [{"name": t.name, "lat": t.lat, "lon": t.lon} for t in revealed]
    result["revealed_count"] = state.revealed_count
    result["total_targets"] = len(targets)
    db.commit()
    return result

  # СБГ / ДРГ — досье старейшины; ДРГ дополнительно получает координату закладки
  result["elder_photo_url"] = target.elder_photo_path
  result["elder_note"] = target.elder_note
  if viewer.code == "drg":
    result["drop_lat"] = target.drop_lat
    result["drop_lon"] = target.drop_lon

  tower_log_event(db, scenario_id, "tower_elder_dossier_viewed", {"target": target.code, "viewer": viewer.code})
  db.commit()
  return result
