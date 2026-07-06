"""Интеграционные тесты API захвата КТ."""

from app.point_codes import stage1_point_code
from app.services.game_service import pause_game
from tests.conftest import auth_header, make_point, make_running_game, make_user


class TestBeginCaptureAPI:
  def test_successful_begin_capture(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True)
    point = make_point(db, name="КТ2")
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
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["hold_elapsed_sec"] >= 0

  def test_wrong_code_rejected(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True)
    point = make_point(db, name="КТ2")
    user = make_user(db, side="A")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": "0000",
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "код" in resp.json()["detail"].lower()

  def test_out_of_radius_rejected(self, client, db):
    make_running_game(db, stage=1, capture_radius_m=15, disable_capture_distance=False, stage1_slots_started=True)
    point = make_point(db, lat=44.529392, lon=132.828296, name="КТ2")
    user = make_user(db, side="A")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": 44.6,
        "lon": 133.0,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "Подойдите" in resp.json()["detail"]

  def test_accuracy_bonus_allows_nearby_capture(self, client, db):
    make_running_game(db, stage=1, capture_radius_m=15, disable_capture_distance=False, stage1_slots_started=True)
    point = make_point(db, lat=44.529392, lon=132.828296, name="КТ2")
    user = make_user(db, side="A")
    # ~20m north — outside 15m radius but within 15+15 accuracy bonus
    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": 44.529572,
        "lon": 132.828296,
        "accuracy": 15,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200

  def test_accuracy_bonus_capped_at_20m(self, client, db):
    make_running_game(db, stage=1, capture_radius_m=15, disable_capture_distance=False, stage1_slots_started=True)
    point = make_point(db, lat=44.529392, lon=132.828296, name="КТ2")
    user = make_user(db, side="A")
    # ~40m north — outside 15+20 effective radius even with huge accuracy
    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": 44.529752,
        "lon": 132.828296,
        "accuracy": 200,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "Подойдите" in resp.json()["detail"]

  def test_distance_check_disabled(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True)
    point = make_point(db, name="КТ2")
    user = make_user(db, side="A")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "A",
        "code": stage1_point_code(point),
        "lat": 0.0,
        "lon": 0.0,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200

  def test_game_not_started(self, client, db):
    point = make_point(db)
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

  def test_game_paused(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True)
    pause_game(db)
    point = make_point(db)
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
    assert "паузе" in resp.json()["detail"].lower()

  def test_already_captured_rejected(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_recapturable=False)
    point = make_point(db, side="A")
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
    assert "стороны" in resp.json()["detail"].lower()

  def test_recapture_allowed_for_enemy(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True, stage1_recapturable=True)
    point = make_point(db, name="КТ2", side="A")
    user = make_user(db, side="B")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "B",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

  def test_recapture_rejected_when_disabled(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True, stage1_recapturable=False)
    point = make_point(db, name="КТ2", side="A")
    user = make_user(db, side="B")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "B",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "захвачена" in resp.json()["detail"].lower()

  def test_wrong_side_forbidden(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True)
    point = make_point(db)
    user = make_user(db, side="A")

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "B",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 403


class TestBeginCaptureSchedule:
  def test_capture_blocked_when_idle(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True)
    point = make_point(db, name="КТ2")
    user = make_user(db, side="A")
    from app.point_codes import stage1_point_code

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
    assert "слот" in resp.json()["detail"].lower()

  def test_recapture_slot1_point_in_slot2(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True, stage1_slots_started_minutes_ago=130)
    point = make_point(db, name="КТ2", side="A")
    user = make_user(db, side="B")
    from app.point_codes import stage1_point_code

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": point.id,
        "side": "B",
        "code": stage1_point_code(point),
        "lat": point.lat,
        "lon": point.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200

  def test_capture_blocked_outside_slot(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True)
    point = make_point(db, name="КТ1")
    user = make_user(db, side="A")
    from app.point_codes import stage1_point_code

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
    assert "слот" in resp.json()["detail"].lower()


class TestHoldConfirmAPI:
  def test_hold_ping_updates_session(self, client, db):
    make_running_game(db, stage=1, disable_capture_distance=True, stage1_slots_started=True)
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

    resp = client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "A"},
      headers=auth_header(user),
    )
    assert resp.status_code == 200
    assert resp.json()["hold_ready"] is False

  def test_hold_confirm_without_prior_code_on_stage1_fails(self, client, db):
    make_running_game(db, stage=1)
    point = make_point(db)
    user = make_user(db, side="A")

    resp = client.post(
      "/api/hold/confirm",
      json={"point_id": point.id, "side": "A"},
      headers=auth_header(user),
    )
    assert resp.status_code == 400
