"""Тесты логики удержания и захвата (hold_service)."""

from datetime import datetime, timedelta

import pytest

from app.models import GameState, HoldSession, Point
from app.point_codes import stage1_point_code
from app.services.game_service import pause_game
from app.services.hold_service import (
  HOLD_ALREADY_CAPTURED,
  HOLD_ALREADY_CAPTURED_OURS,
  HOLD_BUSY_OTHER_ENGINEER,
  HOLD_BUSY_OTHER_SIDE,
  assert_can_start_point_hold,
  close_expired_holds,
  confirm_hold,
  get_active_hold,
  is_stage1_captured,
  leave_hold,
  maybe_complete_hold,
  refresh_active_hold_progress,
)
from tests.conftest import make_point, make_running_game, make_user


def _hold_phase_stage1(db, **kwargs):
  make_running_game(db, stage=1, stage1_slots_started=True, **kwargs)
  make_point(db, name="КТ2")
  make_user(db)


class TestStage1CaptureBasics:
  def test_stage1_not_captured_initially(self, db):
    point = make_point(db)
    assert not is_stage1_captured(point)

  def test_cannot_start_on_captured_point_other_side(self, db):
    point = make_point(db, side="A")
    with pytest.raises(ValueError, match=HOLD_ALREADY_CAPTURED):
      assert_can_start_point_hold(point, "B", None)

  def test_can_start_recapture_when_enabled(self, db):
    _hold_phase_stage1(db, stage1_recapturable=True)
    point = db.query(Point).filter_by(id=1).first()
    point.side = "A"
    db.commit()
    game = db.query(GameState).filter_by(id=1).first()
    assert_can_start_point_hold(point, "B", game)

  def test_cannot_start_recapture_when_disabled(self, db):
    _hold_phase_stage1(db, stage1_recapturable=False)
    point = db.query(Point).filter_by(id=1).first()
    point.side = "A"
    db.commit()
    game = db.query(GameState).filter_by(id=1).first()
    with pytest.raises(ValueError, match=HOLD_ALREADY_CAPTURED):
      assert_can_start_point_hold(point, "B", game)

  def test_cannot_start_on_captured_point_same_side(self, db):
    point = make_point(db, side="A")
    with pytest.raises(ValueError, match=HOLD_ALREADY_CAPTURED_OURS):
      assert_can_start_point_hold(point, "A", None)

  def test_stage1_requires_code_before_hold(self, db):
    make_running_game(db, stage=1, point_capture_seconds=60)
    make_point(db)
    make_user(db, user_id=1, username="eng_a1", side="A")

    with pytest.raises(ValueError, match="код"):
      confirm_hold(db, 1, "A", 1)

  def test_stage1_start_with_code_flag(self, db):
    _hold_phase_stage1(db, point_capture_seconds=60)

    session, created = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    assert created
    assert session.active
    assert get_active_hold(db, 1) is not None

  def test_capture_completes_after_required_time(self, db):
    _hold_phase_stage1(db, point_capture_seconds=60)
    point = db.query(Point).filter_by(id=1).first()

    session, _ = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session.started_at = datetime.utcnow() - timedelta(seconds=61)
    session.last_ping_at = datetime.utcnow()
    db.commit()

    event = maybe_complete_hold(db, point, session)
    db.refresh(point)
    db.refresh(session)

    assert event == "point_capture"
    assert point.side == "A"
    assert not session.active
    assert is_stage1_captured(point)

  def test_recapture_completes_and_changes_owner(self, db):
    _hold_phase_stage1(db, point_capture_seconds=60, stage1_recapturable=True)
    make_user(db, user_id=2, username="eng_b1", side="B")
    point = db.query(Point).filter_by(id=1).first()
    point.side = "A"
    db.commit()

    session, created = confirm_hold(db, 1, "B", 2, allow_stage1_start=True)
    assert created
    session.started_at = datetime.utcnow() - timedelta(seconds=61)
    session.last_ping_at = datetime.utcnow()
    db.commit()

    event = maybe_complete_hold(db, point, session)
    db.refresh(point)

    assert event == "point_recapture"
    assert point.side == "B"

  def test_capture_not_complete_before_required_time(self, db):
    _hold_phase_stage1(db, point_capture_seconds=120)
    point = db.query(Point).filter_by(id=1).first()

    session, _ = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session.started_at = datetime.utcnow() - timedelta(seconds=30)
    db.commit()

    event = maybe_complete_hold(db, point, session)
    db.refresh(point)

    assert event is None
    assert point.side is None


class TestHoldConflicts:
  def test_other_side_blocked(self, db):
    _hold_phase_stage1(db)
    make_user(db, user_id=2, username="eng_b1", side="B")

    confirm_hold(db, 1, "A", 1, allow_stage1_start=True)

    with pytest.raises(ValueError, match=HOLD_BUSY_OTHER_SIDE):
      confirm_hold(db, 1, "B", 2, allow_stage1_start=True)

  def test_other_engineer_same_side_blocked(self, db):
    _hold_phase_stage1(db)
    make_user(db, user_id=2, username="eng_a2", side="A")

    confirm_hold(db, 1, "A", 1, allow_stage1_start=True)

    with pytest.raises(ValueError, match=HOLD_BUSY_OTHER_ENGINEER):
      confirm_hold(db, 1, "A", 2, allow_stage1_start=True)

  def test_same_engineer_can_ping(self, db):
    _hold_phase_stage1(db)

    confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session, created = confirm_hold(db, 1, "A", 1)
    assert not created
    assert session.active


class TestDeadMan:
  def test_expired_hold_closes_session(self, db):
    _hold_phase_stage1(db, point_hold_ping_seconds=30)

    session, _ = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session.last_ping_at = datetime.utcnow() - timedelta(seconds=31)
    db.commit()

    closed = close_expired_holds(db)
    assert len(closed) == 1
    assert not closed[0].active

    point = db.query(Point).filter_by(id=1).first()
    assert point.side is None

  def test_leave_resets_side_on_stage1(self, db):
    _hold_phase_stage1(db)

    confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    result = leave_hold(db, 1, "A", 1)

    assert result is not None
    point = db.query(Point).filter_by(id=1).first()
    assert point.side is None

  def test_leave_does_not_reset_captured_point(self, db):
    _hold_phase_stage1(db, point_capture_seconds=30)
    point = db.query(Point).filter_by(id=1).first()

    session, _ = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session.started_at = datetime.utcnow() - timedelta(seconds=31)
    maybe_complete_hold(db, point, session)
    db.commit()
    db.refresh(point)
    assert point.side == "A"

    # Зависшая сессия после захвата
    stale = HoldSession(
      point_id=1,
      side="A",
      user_id=1,
      started_at=datetime.utcnow(),
      last_ping_at=datetime.utcnow(),
      active=True,
    )
    db.add(stale)
    db.commit()

    leave_hold(db, 1, "A", 1)
    db.refresh(point)
    assert point.side == "A"


class TestStage3Hold:
  def test_stage3_hold_becomes_ready(self, db):
    make_running_game(db, stage=3, post_hold_seconds=60)
    point = make_point(db, stage=3)
    make_user(db)

    session, created = confirm_hold(db, 1, "A", 1, allow_stage3_start=True)
    assert created
    assert point.side == "A"

    session.started_at = datetime.utcnow() - timedelta(seconds=61)
    db.commit()

    event = maybe_complete_hold(db, point, session)
    db.refresh(session)

    assert event == "point_hold_ready"
    assert session.hold_ready
    assert session.active
    assert point.side == "A"


class TestGameState:
  def test_paused_game_blocks_hold(self, db):
    make_running_game(db, stage=1)
    make_point(db)
    make_user(db)
    pause_game(db)

    with pytest.raises(ValueError, match="паузе"):
      confirm_hold(db, 1, "A", 1, allow_stage1_start=True)

  def test_refresh_active_hold_progress_completes_stale_holds(self, db):
    _hold_phase_stage1(db, point_capture_seconds=30)
    point = db.query(Point).filter_by(id=1).first()

    session, _ = confirm_hold(db, 1, "A", 1, allow_stage1_start=True)
    session.started_at = datetime.utcnow() - timedelta(seconds=35)
    db.commit()

    events = refresh_active_hold_progress(db)
    db.refresh(point)

    assert any(e["e"] == "point_capture" for e in events)
    assert point.side == "A"


class TestPointCodes:
  def test_stage1_code_format(self, db):
    point = make_point(db, point_id=3)
    assert stage1_point_code(point) == "4003"
