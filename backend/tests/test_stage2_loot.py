"""Тесты этапа 2: выдача лута, видеоотчёт, доставка на базу."""

from app.services.stage2_assignment_service import (
  get_issued_cache_ids,
  is_cache_issued,
  issue_next_assignment,
)
from tests.conftest import (
  auth_header,
  make_cache,
  make_landmark,
  make_point,
  make_running_game,
  make_user,
)

FAKE_MP4 = ("report.mp4", b"\x00" * 256, "video/mp4")
FAKE_JPG = ("base.jpg", b"\xff\xd8\xff" + b"\x00" * 256, "image/jpeg")


def _breach_code(client, cache_obj, user):
  return client.post(
    "/api/cache/breach-code",
    json={
      "cache_id": cache_obj.id,
      "side": "A",
      "code": cache_obj.detonation_code,
      "qr_token": cache_obj.qr_token,
      "lat": cache_obj.lat,
      "lon": cache_obj.lon,
    },
    headers=auth_header(user),
  )


def _film_report(client, cache_obj, user):
  return client.post(
    "/api/cache/film-report",
    data={
      "cache_id": cache_obj.id,
      "side": "A",
      "lat": cache_obj.lat,
      "lon": cache_obj.lon,
      "qr_token": cache_obj.qr_token,
    },
    files={"file": FAKE_MP4},
    headers=auth_header(user),
  )


def _deliver_report(client, cache_obj, user, lat, lon, side="A"):
  return client.post(
    "/api/cache/deliver-report",
    data={
      "cache_id": cache_obj.id,
      "side": side,
      "lat": lat,
      "lon": lon,
      "qr_token": cache_obj.qr_token,
    },
    files={"file": FAKE_JPG},
    headers=auth_header(user),
  )


class TestStage2Assignment:
  def test_issue_next_assignment(self, db):
    make_running_game(db, stage=2)
    make_cache(db, cache_id=1)
    make_cache(db, cache_id=2, name="Ящик-2", detonation_code="1002")

    assignment = issue_next_assignment(db)
    assert assignment is not None
    assert assignment.cache_id in {1, 2}
    assert is_cache_issued(db, assignment.cache_id)

  def test_issue_skips_disabled_caches(self, db):
    make_running_game(db, stage=2)
    make_cache(db, cache_id=1, enabled=False)
    make_cache(db, cache_id=2, name="Ящик-2", detonation_code="1002", enabled=True)

    assignment = issue_next_assignment(db)
    assert assignment is not None
    assert assignment.cache_id == 2

  def test_issue_skips_already_issued(self, db):
    make_running_game(db, stage=2)
    make_cache(db, cache_id=1)
    make_cache(db, cache_id=2, name="Ящик-2", detonation_code="1002")

    first = issue_next_assignment(db)
    second = issue_next_assignment(db)
    assert first.cache_id != second.cache_id
    assert len(get_issued_cache_ids(db)) == 2


class TestStage2FilmReportAPI:
  def test_report_without_issue_forbidden(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")

    resp = client.post(
      "/api/cache/film-report",
      data={
        "cache_id": cache_obj.id,
        "side": "A",
        "lat": cache_obj.lat,
        "lon": cache_obj.lon,
        "qr_token": cache_obj.qr_token,
      },
      files={"file": FAKE_MP4},
      headers=auth_header(user),
    )
    assert resp.status_code == 403
    assert "не выдана" in resp.json()["detail"].lower()

  def test_report_without_code_rejected(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    resp = _film_report(client, cache_obj, user)
    assert resp.status_code == 400
    assert "код" in resp.json()["detail"].lower()

  def test_report_with_video(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    assert _breach_code(client, cache_obj, user).status_code == 200
    resp = _film_report(client, cache_obj, user)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["bonus"] == 150
    assert data["next_step"] == "deliver"
    assert "подрыв" in data["message"].lower() or "видео" in data["message"].lower()

  def test_report_without_geofence(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=False)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    _breach_code(client, cache_obj, user)
    resp = client.post(
      "/api/cache/film-report",
      data={
        "cache_id": cache_obj.id,
        "side": "A",
        "lat": 0.0,
        "lon": 0.0,
        "qr_token": cache_obj.qr_token,
      },
      files={"file": FAKE_MP4},
      headers=auth_header(user),
    )
    assert resp.status_code == 200

  def test_report_requires_video(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    _breach_code(client, cache_obj, user)
    resp = client.post(
      "/api/cache/film-report",
      data={
        "cache_id": cache_obj.id,
        "side": "A",
        "lat": cache_obj.lat,
        "lon": cache_obj.lon,
        "qr_token": cache_obj.qr_token,
      },
      files={"file": ("photo.jpg", b"\xff\xd8\xff", "image/jpeg")},
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "видео" in resp.json()["detail"].lower()

  def test_report_posts_to_chat(self, client, db):
    from app.models import ChatMessage

    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    _breach_code(client, cache_obj, user)
    resp = _film_report(client, cache_obj, user)
    assert resp.status_code == 200

    msgs = db.query(ChatMessage).filter(ChatMessage.side == "A").all()
    assert len(msgs) == 1
    assert msgs[0].thread == "cmd"
    assert msgs[0].media_type == "video"

  def test_admin_confirm_without_video(self, db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    make_running_game(db, stage=2)
    cache_obj = make_cache(db)
    admin = make_user(db, user_id=10, username="admin", role="admin", side=None)
    issue_next_assignment(db)

    def override_get_db():
      yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
      api = TestClient(app)
      resp = api.post(
        f"/api/admin/cache/{cache_obj.id}/confirm",
        json={"side": "A"},
        headers=auth_header(admin),
      )
      assert resp.status_code == 200
      db.refresh(cache_obj)
      assert cache_obj.destroyed is True
      assert cache_obj.destroyed_by_side == "A"
      assert cache_obj.admin_confirmed is True
    finally:
      app.dependency_overrides.clear()

  def test_report_twice_rejected(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    _breach_code(client, cache_obj, user)
    assert _film_report(client, cache_obj, user).status_code == 200

    resp = _film_report(client, cache_obj, user)
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "вскрыта" in detail or "код" in detail

  def test_detonate_film_rejected(self, client, db):
    make_running_game(db, stage=2)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    resp = client.post(
      "/api/cache/detonate",
      json={"cache_id": cache_obj.id, "side": "A", "code": cache_obj.detonation_code},
      headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "qr" in resp.json()["detail"].lower()

  def test_unlock_box_direct(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db, loot_variant="box_direct")
    user = make_user(db, side="A")
    issue_next_assignment(db)

    resp = client.post(
      "/api/cache/unlock-code",
      json={
        "cache_id": cache_obj.id,
        "side": "A",
        "code": cache_obj.detonation_code,
        "qr_token": cache_obj.qr_token,
        "lat": cache_obj.lat,
        "lon": cache_obj.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200
    db.refresh(cache_obj)
    assert cache_obj.destroyed is True

  def test_parallel_stage1_capture_with_stage2(self, client, db):
    from app.point_codes import stage1_point_code

    make_running_game(db, stage=1, stage2_enabled=True, disable_capture_distance=True, stage1_slots_started=True)
    user = make_user(db, side="A")
    make_cache(db)
    pt = make_point(db, name="КТ2")
    issue_next_assignment(db)

    resp = client.post(
      "/api/point/begin-capture",
      json={
        "point_id": pt.id,
        "side": "A",
        "code": stage1_point_code(pt),
        "lat": pt.lat,
        "lon": pt.lon,
      },
      headers=auth_header(user),
    )
    assert resp.status_code == 200


class TestStage2Schedule:
  def test_non_engineer_breach_forbidden(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    commander = make_user(db, user_id=2, username="cmd_a", role="commander", side="A")
    issue_next_assignment(db)

    resp = client.post(
      "/api/cache/breach-code",
      json={
        "cache_id": cache_obj.id,
        "side": "A",
        "code": cache_obj.detonation_code,
        "qr_token": cache_obj.qr_token,
        "lat": cache_obj.lat,
        "lon": cache_obj.lon,
      },
      headers=auth_header(commander),
    )
    assert resp.status_code == 403


class TestStage2DeliverAPI:
  def _report(self, client, db, cache_obj, user):
    issue_next_assignment(db)
    _breach_code(client, cache_obj, user)
    _film_report(client, cache_obj, user)

  def _confirm_delivery(self, client, db, cache_id, admin):
    return client.post(
      f"/api/admin/cache/{cache_id}/confirm-delivery",
      headers=auth_header(admin),
    )

  def test_deliver_without_breach_rejected(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    base = make_landmark(db)
    user = make_user(db, side="A")
    issue_next_assignment(db)

    resp = _deliver_report(client, cache_obj, user, base.lat, base.lon)
    assert resp.status_code == 400
    assert "код" in resp.json()["detail"].lower() or "плёнку" in resp.json()["detail"].lower()

  def test_deliver_wrong_side_rejected(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    make_landmark(db)
    user_a = make_user(db, user_id=1, username="eng_a1", side="A")
    user_b = make_user(db, user_id=2, username="eng_b1", side="B")
    self._report(client, db, cache_obj, user_a)

    resp = _deliver_report(client, cache_obj, user_b, 44.53, 132.83, side="B")
    assert resp.status_code == 403

  def test_deliver_report_at_base_pending_admin(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    base = make_landmark(db)
    user = make_user(db, side="A")
    self._report(client, db, cache_obj, user)

    resp = _deliver_report(client, cache_obj, user, base.lat, base.lon)
    assert resp.status_code == 200
    assert "фотоотчёт" in resp.json()["message"].lower()
    db.refresh(cache_obj)
    assert cache_obj.delivery_reported_at is not None
    assert cache_obj.delivered_at is None

  def test_deliver_report_without_geofence(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=False)
    cache_obj = make_cache(db)
    user = make_user(db, side="A")
    self._report(client, db, cache_obj, user)

    resp = _deliver_report(client, cache_obj, user, 0.0, 0.0)
    assert resp.status_code == 200

  def test_deliver_confirm_by_admin(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    base = make_landmark(db)
    user = make_user(db, side="A")
    admin = make_user(db, user_id=10, username="admin", role="admin", side=None)
    self._report(client, db, cache_obj, user)

    assert _deliver_report(client, cache_obj, user, base.lat, base.lon).status_code == 200

    resp = self._confirm_delivery(client, db, cache_obj.id, admin)
    assert resp.status_code == 200
    db.refresh(cache_obj)
    assert cache_obj.delivered_at is not None

  def test_admin_confirm_delivery_without_photo(self, db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    make_running_game(db, stage=2)
    cache_obj = make_cache(db)
    admin = make_user(db, user_id=10, username="admin", role="admin", side=None)
    issue_next_assignment(db)
    cache_obj.destroyed = True
    cache_obj.destroyed_by_side = "A"
    db.commit()

    def override_get_db():
      yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
      api = TestClient(app)
      resp = api.post(
        f"/api/admin/cache/{cache_obj.id}/confirm-delivery",
        json={"side": "A"},
        headers=auth_header(admin),
      )
      assert resp.status_code == 200
      db.refresh(cache_obj)
      assert cache_obj.delivery_reported_at is not None
      assert cache_obj.delivered_at is not None
      assert cache_obj.delivered_by_side == "A"
    finally:
      app.dependency_overrides.clear()

  def test_deliver_twice_rejected(self, client, db):
    make_running_game(db, stage=2, disable_capture_distance=True)
    cache_obj = make_cache(db)
    base = make_landmark(db)
    user = make_user(db, side="A")
    admin = make_user(db, user_id=10, username="admin", role="admin", side=None)
    self._report(client, db, cache_obj, user)

    payload = {
      "data": {
        "cache_id": cache_obj.id,
        "side": "A",
        "lat": base.lat,
        "lon": base.lon,
        "qr_token": cache_obj.qr_token,
      },
      "files": {"file": FAKE_JPG},
      "headers": auth_header(user),
    }
    assert client.post("/api/cache/deliver-report", **payload).status_code == 200
    assert self._confirm_delivery(client, db, cache_obj.id, admin).status_code == 200

    resp = client.post("/api/cache/deliver-report", **payload)
    assert resp.status_code == 400
    assert "сдан" in resp.json()["detail"].lower()
