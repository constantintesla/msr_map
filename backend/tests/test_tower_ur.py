"""Тесты синхронного захвата укрепрайона (app/tower/ur_service.py)."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Scenario
from app.tower.config_service import get_tower_config
from app.tower.models import UrPoint, UrZone
from app.tower.ur_service import scan_drg_ur_point, scan_sbg_ur_point


def _make_scenario_with_zone(db: Session, *, sync_window_s: int = 180, hold_s: int = 1200):
  scenario = Scenario(id=1, name="Башня", slug="bashnya", is_active=True)
  db.add(scenario)
  db.commit()
  cfg = get_tower_config(db, scenario.id)
  cfg.ur_sync_window_seconds = sync_window_s
  cfg.ur_hold_seconds = hold_s
  db.commit()

  zone = UrZone(scenario_id=scenario.id, name="УР1", order=0, status="idle")
  db.add(zone)
  db.commit()
  db.refresh(zone)

  points = []
  for i in range(1, 4):
    p = UrPoint(scenario_id=scenario.id, zone_id=zone.id, name=f"КПП1-{i}", lat=44.0, lon=131.0)
    db.add(p)
    points.append(p)
  db.commit()
  for p in points:
    db.refresh(p)
  return scenario.id, zone.id, points


def test_three_scans_by_three_different_people_within_window_start_holding(db: Session):
  scenario_id, zone_id, points = _make_scenario_with_zone(db)
  now = datetime.utcnow()

  zone = scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  assert zone.status == "syncing"
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now + timedelta(seconds=60)
  )
  assert zone.status == "syncing"
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now + timedelta(seconds=120)
  )
  assert zone.status == "holding"
  assert zone.hold_started_at is not None


def test_same_person_scanning_all_three_does_not_start_holding(db: Session):
  """Один человек, обежавший все три точки, не должен запускать таймер удержания —
  мастер явно требует трёх РАЗНЫХ людей."""
  scenario_id, zone_id, points = _make_scenario_with_zone(db)
  now = datetime.utcnow()

  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[1], scanner_user_id=1, now=now + timedelta(seconds=30))
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=1, now=now + timedelta(seconds=60)
  )
  assert zone.status == "syncing"
  assert zone.hold_started_at is None

  # другой человек пересканирует одну из точек — всё ещё только двое разных
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now + timedelta(seconds=70)
  )
  assert zone.status == "syncing"
  assert zone.hold_started_at is None

  # третий, действительно другой человек — теперь трое разных, запускаем таймер
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now + timedelta(seconds=90)
  )
  assert zone.status == "holding"


def test_scan_outside_window_resets_to_idle(db: Session):
  scenario_id, zone_id, points = _make_scenario_with_zone(db, sync_window_s=180)
  now = datetime.utcnow()

  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now + timedelta(seconds=60))
  # третья точка отсканирована слишком поздно — окно от первого скана истекло
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now + timedelta(seconds=300)
  )
  assert zone.status == "idle"
  for p in db.query(UrPoint).filter(UrPoint.zone_id == zone_id).all():
    assert p.last_sbg_scan_at is None
    assert p.last_sbg_scan_by is None


def test_hold_completes_after_timer(db: Session):
  from app.tower.ur_service import refresh_all_zones

  scenario_id, zone_id, points = _make_scenario_with_zone(db, hold_s=1200)
  now = datetime.utcnow()
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now + timedelta(seconds=30))
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now + timedelta(seconds=60)
  )
  assert zone.status == "holding"

  zones = refresh_all_zones(db, scenario_id, now=now + timedelta(seconds=60 + 1201))
  assert zones[0].status == "captured"
  assert zones[0].captured_at is not None


def test_drg_scan_resets_during_syncing(db: Session):
  scenario_id, zone_id, points = _make_scenario_with_zone(db)
  now = datetime.utcnow()
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)

  zone = scan_drg_ur_point(db, scenario_id=scenario_id, point=points[0], now=now + timedelta(seconds=30))
  assert zone.status == "idle"
  assert points[0].last_sbg_scan_at is None
  assert points[0].last_sbg_scan_by is None


def test_drg_scan_resets_during_holding(db: Session):
  scenario_id, zone_id, points = _make_scenario_with_zone(db)
  now = datetime.utcnow()
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now + timedelta(seconds=10))
  zone = scan_sbg_ur_point(
    db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now + timedelta(seconds=20)
  )
  assert zone.status == "holding"

  zone = scan_drg_ur_point(db, scenario_id=scenario_id, point=points[1], now=now + timedelta(seconds=100))
  assert zone.status == "idle"
  assert zone.hold_started_at is None
  for p in db.query(UrPoint).filter(UrPoint.zone_id == zone_id).all():
    assert p.last_sbg_scan_at is None
    assert p.last_sbg_scan_by is None


def test_drg_scan_after_capture_is_noop(db: Session):
  from app.tower.ur_service import refresh_all_zones

  scenario_id, zone_id, points = _make_scenario_with_zone(db, hold_s=60)
  now = datetime.utcnow()
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[0], scanner_user_id=1, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[1], scanner_user_id=2, now=now)
  scan_sbg_ur_point(db, scenario_id=scenario_id, point=points[2], scanner_user_id=3, now=now)
  refresh_all_zones(db, scenario_id, now=now + timedelta(seconds=61))

  zone = scan_drg_ur_point(db, scenario_id=scenario_id, point=points[0], now=now + timedelta(seconds=70))
  assert zone.status == "captured"
