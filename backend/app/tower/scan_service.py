"""Диспетчер сканирования: резолвит QR-токен/ручной код в деревенскую доску
или точку КПП и вызывает нужный сервис (reveal_service / ur_service)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import User
from app.tower.config_service import get_tower_config
from app.tower.models import Faction, UrPoint, UrZone
from app.tower.reveal_service import scan_village_board
from app.tower.ur_service import scan_drg_ur_point, scan_sbg_ur_point


def resolve_scan_target(db: Session, *, token: str | None, code: str | None):
  """Резолвит глобально по токену/коду — без привязки к «активному» сценарию
  движка: qr_token/join_token/manual_code уникальны сами по себе (unique=True
  на Faction/UrPoint), а Башня должна работать независимо от того, что сейчас
  выставлено активным в общем переключателе сценариев."""
  if token:
    faction = db.query(Faction).filter(Faction.qr_token == token).first()
    if faction:
      return "village", faction
    point = db.query(UrPoint).filter(UrPoint.qr_token == token).first()
    if point:
      return "ur_point", point
  if code:
    faction = db.query(Faction).filter(Faction.manual_code == code).first()
    if faction:
      return "village", faction
    point = db.query(UrPoint).filter(UrPoint.manual_code == code).first()
    if point:
      return "ur_point", point
  return None, None


def zone_to_dict(db: Session, zone: UrZone) -> dict:
  cfg = get_tower_config(db, zone.scenario_id)
  points = db.query(UrPoint).filter(UrPoint.zone_id == zone.id).order_by(UrPoint.id).all()
  hold_ends_at = None
  if zone.status == "holding" and zone.hold_started_at:
    hold_ends_at = zone.hold_started_at + timedelta(seconds=cfg.ur_hold_seconds)
  return {
    "zone_id": zone.id,
    "zone_name": zone.name,
    "status": zone.status,
    "sync_started_at": zone.sync_started_at,
    "hold_started_at": zone.hold_started_at,
    "hold_ends_at": hold_ends_at,
    "captured_at": zone.captured_at,
    "points": [
      {"id": p.id, "name": p.name, "scanned": p.last_sbg_scan_at is not None} for p in points
    ],
  }


def perform_scan(
  db: Session,
  *,
  scanner: User,
  token: str | None,
  code: str | None,
) -> tuple[str, dict]:
  kind, obj = resolve_scan_target(db, token=token, code=code)
  if obj is None:
    raise ValueError("Табличка не найдена")
  scenario_id = obj.scenario_id

  scanner_faction = db.query(Faction).filter(Faction.id == scanner.faction_id).first()
  if scanner_faction is None:
    raise ValueError("У аккаунта нет стороны")

  if kind == "village":
    return "village", scan_village_board(
      db, scenario_id=scenario_id, viewer=scanner_faction, target=obj
    )

  if scanner_faction.code == "sbg":
    zone = scan_sbg_ur_point(db, scenario_id=scenario_id, point=obj, scanner_user_id=scanner.id)
  elif scanner_faction.code == "drg":
    zone = scan_drg_ur_point(db, scenario_id=scenario_id, point=obj)
  else:
    raise ValueError("Эта точка не для вашей стороны")

  return "ur_zone", zone_to_dict(db, zone)
