"""Тесты расписания этапа 1 (ручной старт, далее по таймеру)."""

from datetime import datetime, timedelta

from app.services.stage1_schedule_service import (
  get_active_kt_numbers,
  get_stage1_phase,
  is_point_capturable,
  kt_number_from_name,
  start_stage1_slot,
)
from tests.conftest import make_point, make_running_game


class TestStage1Schedule:
  def test_kt_number_from_name(self):
    assert kt_number_from_name("КТ1 (второй этаж)") == 1
    assert kt_number_from_name("КТ12") == 12
    assert kt_number_from_name("Пост") is None

  def test_idle_before_slot_start(self, db):
    game = make_running_game(db, stage=1)
    assert get_stage1_phase(game) == "idle"
    assert get_active_kt_numbers(game) == set()

  def test_hold_phase_first_slot(self, db):
    game = make_running_game(db, stage=1)
    start_stage1_slot(db, game)
    assert get_stage1_phase(game) == "hold"
    assert get_active_kt_numbers(game) == {2, 3, 6, 8, 10}

  def test_hold_phase_second_slot_by_timer(self, db):
    game = make_running_game(db, stage=1, stage1_slots_started=True, stage1_slots_started_minutes_ago=130)
    assert get_stage1_phase(game) == "hold"
    assert get_active_kt_numbers(game) == {4, 5, 9, 11, 12}

  def test_is_point_capturable(self, db):
    game = make_running_game(db, stage=1, stage1_slots_started=True)
    p_active = make_point(db, point_id=2, name="КТ2")
    p_inactive = make_point(db, point_id=1, name="КТ1")
    assert is_point_capturable(p_active, game) is True
    assert is_point_capturable(p_inactive, game) is False

  def test_idle_blocks_capture(self, db):
    game = make_running_game(db, stage=1)
    point = make_point(db, name="КТ2")
    assert is_point_capturable(point, game) is False

  def test_ended_after_last_slot(self, db):
    game = make_running_game(db, stage=1, stage1_slots_started=True, stage1_slots_started_minutes_ago=400)
    assert get_stage1_phase(game) == "ended"
    assert get_active_kt_numbers(game) == set()

  def test_captured_from_slot1_recapturable_in_slot2(self, db):
    from app.services.stage1_schedule_service import is_captured_carryover_to_slot, is_point_capturable

    game = make_running_game(db, stage=1, stage1_slots_started=True, stage1_slots_started_minutes_ago=130)
    p = make_point(db, point_id=2, name="КТ2", side="A")
    assert is_captured_carryover_to_slot(p, game) is True
    assert is_point_capturable(p, game) is True

  def test_uncaptured_slot1_not_available_in_slot2(self, db):
    from app.services.stage1_schedule_service import is_point_capturable

    game = make_running_game(db, stage=1, stage1_slots_started=True, stage1_slots_started_minutes_ago=130)
    p = make_point(db, point_id=1, name="КТ1")
    assert is_point_capturable(p, game) is False
