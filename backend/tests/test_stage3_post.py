"""Тесты этапа 3: штурм поста (код → удержание → видео ОК)."""

from datetime import datetime, timedelta

import pytest

from app.models import HoldSession
from app.point_codes import stage1_point_code
from app.services.hold_service import POST_ASSAULT_CODE_FIRST, POST_SBG_PASSIVE, confirm_hold, require_point_hold_ready
from tests.conftest import (
  auth_header,
  make_point,
  make_running_game,
  make_user,
)

FAKE_MP4 = ("report.mp4", b"\x00" * 256, "video/mp4")


class TestStage3HoldService:
  def test_post_hold_becomes_ready(self, db):
    make_running_game(db, stage=3, post_hold_seconds=60)
    point = make_point(db, stage=3, name="Пост-1")
    make_user(db)

    session, created = confirm_hold(db, point.id, "A", 1, allow_stage3_start=True)
    assert created
    assert point.side == "A"

    session.started_at = datetime.utcnow() - timedelta(seconds=61)
    db.commit()

    session, _ = confirm_hold(db, point.id, "A", 1)
    assert session.hold_ready is True

  def test_post_hold_requires_begin_capture(self, db):
    make_running_game(db, stage=3, post_hold_seconds=600)
    point = make_point(db, stage=3)
    make_user(db)

    with pytest.raises(ValueError, match=POST_ASSAULT_CODE_FIRST):
      confirm_hold(db, point.id, "A", 1)

  def test_post_hold_sbg_forbidden(self, db):
    make_running_game(db, stage=3, post_hold_seconds=600)
    point = make_point(db, stage=3)
    make_user(db)

    with pytest.raises(ValueError, match=POST_SBG_PASSIVE):
      confirm_hold(db, point.id, "B", 2, allow_stage3_start=True)

  def test_detonate_requires_hold_ready(self, db):
    make_running_game(db, stage=3, post_hold_seconds=600)
    point = make_point(db, stage=3)
    make_user(db)
    confirm_hold(db, point.id, "A", 1, allow_stage3_start=True)

    with pytest.raises(ValueError, match="До детонации"):
      require_point_hold_ready(db, point.id, "A")


class TestStage3AssaultAPI:
  def _ready_post(self, client, db, point, user):
    make_running_game(db, stage=3, post_hold_seconds=60, disable_capture_distance=True)
    client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    session = db.query(HoldSession).filter(HoldSession.point_id == point.id).first()
    session.started_at = datetime.utcnow() - timedelta(seconds=61)
    db.commit()
    client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "A"},
      headers=auth_header(user),
    )

  def test_hold_without_begin_capture_rejected(self, client, db):
    make_running_game(db, stage=3)
    point = make_point(db, stage=3, detonation_code="3001")
    user = make_user(db, side="A")

    resp = client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "A"},
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "штурм" in resp.json()["detail"].lower()

  def test_hold_side_b_forbidden(self, client, db):
    make_running_game(db, stage=3)
    point = make_point(db, stage=3, detonation_code="3001")
    user_b = make_user(db, user_id=2, username="eng_b1", side="B")

    resp = client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "B"},
      headers=auth_header(user_b),
    )
    assert resp.status_code == 403

  def test_detonate_deprecated(self, client, db):
    point = make_point(db, stage=3, detonation_code="3001")
    user = make_user(db, side="A")
    self._ready_post(client, db, point, user)

    resp = client.post(
      "/api/point/detonate",
      json={"point_id": point.id, "side": "A", "code": "3001"},
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "видео" in resp.json()["detail"].lower()

  def test_post_film_report_success(self, client, db):
    point = make_point(db, stage=3, detonation_code="3001")
    user = make_user(db, side="A")
    self._ready_post(client, db, point, user)

    resp = client.post(
      "/api/point/post-film-report",
      headers=auth_header(user),
      data={
        "point_id": point.id,
        "side": "A",
        "lat": point.lat,
        "lon": point.lon,
      },
      files={"file": FAKE_MP4},
    )
    assert resp.status_code == 200
    assert resp.json()["bonus"] == 1000

    db.refresh(point)
    assert point.destroyed is True
    assert point.admin_confirmed is False

  def test_post_film_report_side_b_forbidden(self, client, db):
    point = make_point(db, stage=3, detonation_code="3001")
    user_b = make_user(db, user_id=2, username="eng_b1", side="B")
    self._ready_post(client, db, point, make_user(db, side="A"))

    resp = client.post(
      "/api/point/post-film-report",
      headers=auth_header(user_b),
      data={
        "point_id": point.id,
        "side": "B",
        "lat": point.lat,
        "lon": point.lon,
      },
      files={"file": FAKE_MP4},
    )
    assert resp.status_code == 403

  def test_assault_destroyed_post_rejected(self, client, db):
    make_running_game(db, stage=3)
    point = make_point(db, stage=3, detonation_code="3001")
    point.destroyed = True
    db.commit()
    user = make_user(db, side="A")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "подорван" in resp.json()["detail"].lower()

  def test_admin_confirm_after_video(self, client, db):
    point = make_point(db, stage=3, detonation_code="3001")
    user = make_user(db, side="A")
    admin = make_user(db, user_id=99, username="admin1", role="admin", side=None)
    self._ready_post(client, db, point, user)

    assert (
      client.post(
        "/api/point/post-film-report",
        headers=auth_header(user),
        data={"point_id": point.id, "side": "A", "lat": point.lat, "lon": point.lon},
        files={"file": FAKE_MP4},
      ).status_code
      == 200
    )

    resp = client.post(f"/api/admin/point/{point.id}/confirm", headers=auth_header(admin))
    assert resp.status_code == 200

    db.refresh(point)
    assert point.admin_confirmed is True


class TestHoldConfirmOrderFix:
  def test_capture_completes_via_hold_confirm_after_timer(self, client, db):
    make_running_game(db, stage=1, point_capture_seconds=30, disable_capture_distance=True, stage1_slots_started=True)
    point = make_point(db, name="КТ2")
    user = make_user(db, side="A")

    client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )

    session = db.query(HoldSession).filter(HoldSession.point_id == point.id).first()
    session.started_at = datetime.utcnow() - timedelta(seconds=31)
    db.commit()

    resp = client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "A"},
      headers=auth_header(user),
    )
    assert resp.status_code == 200
    assert resp.json()["hold_ready"] is True

    db.refresh(point)
    assert point.side == "A"
