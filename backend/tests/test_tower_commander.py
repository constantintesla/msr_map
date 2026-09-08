"""Тесты командирской консоли Башни: чат/приказы/ростер — faction-scoped
(app/tower/commander_service.py)."""

import pytest
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import Scenario, User
from app.tower import commander_service
from app.tower.models import Faction


def _make_scenario(db: Session) -> int:
  scenario = Scenario(id=1, name="Башня", slug="bashnya", is_active=True)
  db.add(scenario)
  db.commit()
  return scenario.id


def _make_faction(db: Session, scenario_id: int, code: str) -> Faction:
  faction = Faction(scenario_id=scenario_id, code=code, name=code.upper(), kind="ops")
  db.add(faction)
  db.commit()
  db.refresh(faction)
  return faction


def _make_user(db: Session, *, username: str, role: str, faction_id: int) -> User:
  user = User(username=username, password_hash=hash_password("x"), role=role, faction_id=faction_id)
  db.add(user)
  db.commit()
  db.refresh(user)
  return user


def test_chat_visible_only_to_own_faction(db: Session):
  scenario_id = _make_scenario(db)
  sbg = _make_faction(db, scenario_id, "sbg")
  drg = _make_faction(db, scenario_id, "drg")
  cmd_sbg = _make_user(db, username="cmd_sbg", role="commander", faction_id=sbg.id)
  cmd_drg = _make_user(db, username="cmd_drg", role="commander", faction_id=drg.id)

  commander_service.post_chat_message(db, user=cmd_sbg, thread="eng", recipient_username=None, text="Привет СБГ")

  _, sbg_items = commander_service.list_chat_messages(db, user=cmd_sbg, thread="eng")
  assert len(sbg_items) == 1

  _, drg_items = commander_service.list_chat_messages(db, user=cmd_drg, thread="eng")
  assert len(drg_items) == 0


def test_eng_thread_reaches_player_cmd_thread_is_commander_only(db: Session):
  scenario_id = _make_scenario(db)
  sbg = _make_faction(db, scenario_id, "sbg")
  cmd = _make_user(db, username="cmd_sbg", role="commander", faction_id=sbg.id)
  player = _make_user(db, username="ivan", role="faction", faction_id=sbg.id)

  commander_service.post_chat_message(db, user=cmd, thread="eng", recipient_username=None, text="Всем: сбор в 10")
  commander_service.post_chat_message(db, user=cmd, thread="cmd", recipient_username=None, text="Штабу: статус")

  _, player_items = commander_service.list_chat_messages(db, user=player, thread=None)
  assert [m.text for m in player_items] == ["Всем: сбор в 10"]

  _, cmd_items = commander_service.list_chat_messages(db, user=cmd, thread="cmd")
  assert [m.text for m in cmd_items] == ["Штабу: статус"]


def test_order_created_only_for_own_faction_player(db: Session):
  scenario_id = _make_scenario(db)
  sbg = _make_faction(db, scenario_id, "sbg")
  drg = _make_faction(db, scenario_id, "drg")
  cmd_sbg = _make_user(db, username="cmd_sbg", role="commander", faction_id=sbg.id)
  _make_user(db, username="ivan", role="faction", faction_id=drg.id)  # чужой стороны

  with pytest.raises(ValueError):
    commander_service.create_field_order(
      db,
      commander=cmd_sbg,
      target_username="ivan",
      target_name="КПП1-1",
      target_lat=44.0,
      target_lon=131.0,
      note=None,
    )

  own_player = _make_user(db, username="petr", role="faction", faction_id=sbg.id)
  order = commander_service.create_field_order(
    db,
    commander=cmd_sbg,
    target_username="petr",
    target_name="КПП1-1",
    target_lat=44.0,
    target_lon=131.0,
    note=None,
  )
  assert order.engineer_username == "petr"
  assert order.faction_id == sbg.id

  active = commander_service.list_active_orders_for_user(db, own_player)
  assert len(active) == 1


def test_roster_scoped_to_faction(db: Session):
  scenario_id = _make_scenario(db)
  sbg = _make_faction(db, scenario_id, "sbg")
  drg = _make_faction(db, scenario_id, "drg")
  sbg_player = _make_user(db, username="ivan", role="faction", faction_id=sbg.id)
  drg_player = _make_user(db, username="petr", role="faction", faction_id=drg.id)

  commander_service.ping_location(db, sbg_player, 44.0, 131.0, 5.0)
  commander_service.ping_location(db, drg_player, 44.1, 131.1, 5.0)

  sbg_roster = commander_service.list_roster(db, sbg.id)
  assert [r.username for r in sbg_roster] == ["ivan"]

  drg_roster = commander_service.list_roster(db, drg.id)
  assert [r.username for r in drg_roster] == ["petr"]
