"""Тесты раскрытия координат схронов деревни (app/tower/reveal_service.py)."""

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Scenario
from app.tower.config_service import get_tower_config
from app.tower.models import Faction, VillageCacheTarget
from app.tower.reveal_service import scan_village_board


def _make_scenario(db: Session) -> int:
  scenario = Scenario(id=1, name="Башня", slug="bashnya", is_active=True)
  db.add(scenario)
  db.commit()
  return scenario.id


def _make_faction(db: Session, scenario_id: int, *, code: str, kind: str, **extra) -> Faction:
  faction = Faction(scenario_id=scenario_id, code=code, name=code.upper(), kind=kind, **extra)
  db.add(faction)
  db.commit()
  db.refresh(faction)
  return faction


def _set_schedule(db: Session, scenario_id: int, thresholds: list[datetime]) -> None:
  cfg = get_tower_config(db, scenario_id)
  cfg.reveal_schedule_json = json.dumps([t.isoformat() for t in thresholds])
  db.commit()


def test_village_reveal_cumulative_by_schedule(db: Session):
  scenario_id = _make_scenario(db)
  viewer = _make_faction(db, scenario_id, code="korbul", kind="village")
  target = _make_faction(db, scenario_id, code="prvonek", kind="village")
  for i, (name, order) in enumerate([("Д1-1", 1), ("Д1-2", 2), ("Д1-3", 3)]):
    db.add(
      VillageCacheTarget(
        scenario_id=scenario_id, faction_id=target.id, name=name, lat=44.0 + i, lon=131.0 + i, reveal_order=order
      )
    )
  db.commit()

  now = datetime.utcnow()
  _set_schedule(db, scenario_id, [now + timedelta(minutes=30), now + timedelta(minutes=90), now + timedelta(minutes=150)])

  # до первого порога — ничего не раскрыто
  result = scan_village_board(db, scenario_id=scenario_id, viewer=viewer, target=target, now=now)
  assert result["cache_targets"] == []

  # после первого порога — одна координата
  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=viewer, target=target, now=now + timedelta(minutes=31)
  )
  assert [t["name"] for t in result["cache_targets"]] == ["Д1-1"]

  # повторный скан в том же окне — без изменений (идемпотентно)
  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=viewer, target=target, now=now + timedelta(minutes=45)
  )
  assert [t["name"] for t in result["cache_targets"]] == ["Д1-1"]

  # после второго порога — кумулятивно две
  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=viewer, target=target, now=now + timedelta(minutes=91)
  )
  assert [t["name"] for t in result["cache_targets"]] == ["Д1-1", "Д1-2"]

  # после третьего — все три
  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=viewer, target=target, now=now + timedelta(minutes=151)
  )
  assert [t["name"] for t in result["cache_targets"]] == ["Д1-1", "Д1-2", "Д1-3"]


def test_village_reveal_generalized_many_thresholds(db: Session):
  """Универсальность алгоритма: N точек, раскрываемых каждые 15 минут — не только 3/2 часа."""
  scenario_id = _make_scenario(db)
  viewer = _make_faction(db, scenario_id, code="korbul", kind="village")
  target = _make_faction(db, scenario_id, code="prvonek", kind="village")
  names = [f"Т{i}" for i in range(1, 6)]
  for i, name in enumerate(names, start=1):
    db.add(
      VillageCacheTarget(
        scenario_id=scenario_id, faction_id=target.id, name=name, lat=44.0, lon=131.0, reveal_order=i
      )
    )
  db.commit()

  now = datetime.utcnow()
  thresholds = [now + timedelta(minutes=15 * i) for i in range(1, 6)]
  _set_schedule(db, scenario_id, thresholds)

  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=viewer, target=target, now=now + timedelta(minutes=15 * 3 + 1)
  )
  assert len(result["cache_targets"]) == 3


def test_self_scan_blocked(db: Session):
  scenario_id = _make_scenario(db)
  faction = _make_faction(db, scenario_id, code="prvonek", kind="village")
  with pytest.raises(ValueError):
    scan_village_board(db, scenario_id=scenario_id, viewer=faction, target=faction)


def test_ops_factions_get_elder_dossier(db: Session):
  scenario_id = _make_scenario(db)
  target = _make_faction(
    db,
    scenario_id,
    code="prvonek",
    kind="village",
    elder_note="Старейшина: Иван",
    elder_photo_path="elder1.jpg",
    drop_lat=44.5,
    drop_lon=131.5,
  )
  sbg = _make_faction(db, scenario_id, code="sbg", kind="ops")
  drg = _make_faction(db, scenario_id, code="drg", kind="ops")

  sbg_result = scan_village_board(db, scenario_id=scenario_id, viewer=sbg, target=target)
  assert sbg_result["elder_note"] == "Старейшина: Иван"
  assert "drop_lat" not in sbg_result

  drg_result = scan_village_board(db, scenario_id=scenario_id, viewer=drg, target=target)
  assert drg_result["elder_note"] == "Старейшина: Иван"
  assert drg_result["drop_lat"] == 44.5
  assert drg_result["drop_lon"] == 131.5


def test_drg_also_gets_cache_targets_cumulatively(db: Session):
  """ДРГ должна получать те же координаты схронов, что и вражеская деревня — по тому же расписанию."""
  scenario_id = _make_scenario(db)
  target = _make_faction(db, scenario_id, code="prvonek", kind="village", elder_note="Старейшина: Иван")
  drg = _make_faction(db, scenario_id, code="drg", kind="ops")
  for i, (name, order) in enumerate([("Д1-1", 1), ("Д1-2", 2), ("Д1-3", 3)]):
    db.add(
      VillageCacheTarget(
        scenario_id=scenario_id, faction_id=target.id, name=name, lat=44.0 + i, lon=131.0 + i, reveal_order=order
      )
    )
  db.commit()

  now = datetime.utcnow()
  _set_schedule(db, scenario_id, [now + timedelta(minutes=30), now + timedelta(minutes=90)])

  result = scan_village_board(db, scenario_id=scenario_id, viewer=drg, target=target, now=now)
  assert result["cache_targets"] == []
  assert result["elder_note"] == "Старейшина: Иван"

  result = scan_village_board(
    db, scenario_id=scenario_id, viewer=drg, target=target, now=now + timedelta(minutes=31)
  )
  assert [t["name"] for t in result["cache_targets"]] == ["Д1-1"]

  # раскрытие ДРГ отслеживается отдельно от раскрытия вражеской деревне (свой VillageRevealState)
  other_village = _make_faction(db, scenario_id, code="korbul", kind="village")
  village_view = scan_village_board(
    db, scenario_id=scenario_id, viewer=other_village, target=target, now=now + timedelta(minutes=31)
  )
  assert [t["name"] for t in village_view["cache_targets"]] == ["Д1-1"]
