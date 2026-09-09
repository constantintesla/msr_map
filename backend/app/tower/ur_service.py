"""Синхронный захват укрепрайона (УР): 3 точки КПП, СБГ сканирует все три в
пределах короткого окна -> запускается таймер удержания 20 минут -> УР взят.
Обязательно трое РАЗНЫХ людей — один человек, обежавший все три точки,
таймер удержания не запускает. Скан любой из трёх точек стороной ДРГ в любой
момент до захвата — сброс.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.tower.config_service import get_tower_config
from app.tower.events import tower_log_event
from app.tower.models import TowerConfig, UrPoint, UrZone


def _recompute_zone(db: Session, zone: UrZone, cfg: TowerConfig, now: datetime) -> None:
  if zone.status == "captured":
    return

  points = db.query(UrPoint).filter(UrPoint.zone_id == zone.id).all()

  if zone.status == "holding":
    if zone.hold_started_at and now - zone.hold_started_at >= timedelta(seconds=cfg.ur_hold_seconds):
      zone.status = "captured"
      zone.captured_at = now
      tower_log_event(db, zone.scenario_id, "tower_ur_captured", {"zone": zone.name})
    return

  scans = [p.last_sbg_scan_at for p in points if p.last_sbg_scan_at]
  if not scans:
    zone.status = "idle"
    zone.sync_started_at = None
    return

  earliest = min(scans)
  window = timedelta(seconds=cfg.ur_sync_window_seconds)
  scanners = {p.last_sbg_scan_by for p in points if p.last_sbg_scan_by is not None}

  if (
    len(scans) == len(points)
    and (max(scans) - earliest) <= window
    and len(scanners) == len(points)
  ):
    zone.status = "holding"
    zone.hold_started_at = now
    zone.sync_started_at = None
    tower_log_event(db, zone.scenario_id, "tower_ur_holding", {"zone": zone.name})
    return

  if now - earliest > window:
    for p in points:
      p.last_sbg_scan_at = None
      p.last_sbg_scan_by = None
    zone.status = "idle"
    zone.sync_started_at = None
    return

  zone.status = "syncing"
  zone.sync_started_at = earliest


def refresh_all_zones(db: Session, scenario_id: int, now: datetime | None = None) -> list[UrZone]:
  now = now or datetime.utcnow()
  cfg = get_tower_config(db, scenario_id)
  zones = db.query(UrZone).filter(UrZone.scenario_id == scenario_id).order_by(UrZone.order).all()
  for zone in zones:
    if zone.status in ("syncing", "holding"):
      _recompute_zone(db, zone, cfg, now)
  db.commit()
  return zones


def scan_sbg_ur_point(
  db: Session, *, scenario_id: int, point: UrPoint, scanner_user_id: int, now: datetime | None = None
) -> UrZone:
  now = now or datetime.utcnow()
  cfg = get_tower_config(db, scenario_id)
  zone = db.query(UrZone).filter(UrZone.id == point.zone_id).first()
  if zone.status != "captured":
    point.last_sbg_scan_at = now
    point.last_sbg_scan_by = scanner_user_id
    _recompute_zone(db, zone, cfg, now)
  db.commit()
  db.refresh(zone)
  return zone


def scan_drg_ur_point(db: Session, *, scenario_id: int, point: UrPoint, now: datetime | None = None) -> UrZone:
  now = now or datetime.utcnow()
  zone = db.query(UrZone).filter(UrZone.id == point.zone_id).first()
  if zone.status == "captured":
    return zone

  was_active = zone.status in ("syncing", "holding")
  for p in db.query(UrPoint).filter(UrPoint.zone_id == zone.id).all():
    p.last_sbg_scan_at = None
    p.last_sbg_scan_by = None
  zone.status = "idle"
  zone.sync_started_at = None
  zone.hold_started_at = None
  if was_active:
    tower_log_event(db, zone.scenario_id, "tower_ur_recaptured", {"zone": zone.name})
  db.commit()
  db.refresh(zone)
  return zone
