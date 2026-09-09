"""Раскрытие координат схронов деревни.

Схроны деревни физически существуют с самого начала игры (таблички ставятся
до старта). Раскрытие их координат врагу — чисто по расписанию реального
времени: TowerConfig.reveal_schedule_json, отсортированный список
ISO-datetime порогов. Сколько порогов уже наступило — столько схронов (по
порядку reveal_order) уже раскрыто. Это не зависит от того, кто и когда
сканирует табличку — враждебная деревня и ДРГ, сканируя в один момент,
видят одно и то же.
"""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.tower.config_service import get_tower_config
from app.tower.events import tower_log_event
from app.tower.models import Faction, VillageCacheTarget


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

  if viewer.kind == "village" or viewer.code == "drg":
    targets = (
      db.query(VillageCacheTarget)
      .filter(VillageCacheTarget.faction_id == target.id)
      .order_by(VillageCacheTarget.reveal_order)
      .all()
    )
    allowed = min(allowed_reveal_count(db, scenario_id, now), len(targets))
    revealed = targets[:allowed]
    result["cache_targets"] = [{"name": t.name, "lat": t.lat, "lon": t.lon} for t in revealed]
    result["revealed_count"] = allowed
    result["total_targets"] = len(targets)
    tower_log_event(
      db, scenario_id, "tower_village_revealed", {"target": target.code, "viewer": viewer.code, "count": allowed}
    )

  if viewer.kind == "ops":
    from app.tower.media import elder_photo_url

    result["elder_photo_url"] = elder_photo_url(target.elder_photo_path)
    result["elder_note"] = target.elder_note
    tower_log_event(db, scenario_id, "tower_elder_dossier_viewed", {"target": target.code, "viewer": viewer.code})

  db.commit()
  return result
