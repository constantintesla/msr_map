"""Тесты редактирования карты в админке."""

from datetime import datetime

import pytest

from app.models import GameState, GameStatus, HoldSession
from app.models import Cache, Landmark, Point
from app.services import map_edit_service
from tests.conftest import auth_header, make_cache, make_point, make_user


def make_idle_game(db) -> GameState:
  state = GameState(id=1, status=GameStatus.IDLE.value, current_stage=1)
  db.add(state)
  db.commit()
  db.refresh(state)
  return state


class TestMapEditService:
  def test_create_kt_auto_name(self, db):
    make_idle_game(db)
    point = map_edit_service.create_point(db, lat=44.53, lon=132.83, stage=1)
    assert point.name == "КТ1"
    assert point.detonation_code == f"{4000 + point.id:04d}"[-4:]

  def test_create_second_kt(self, db):
    make_idle_game(db)
    make_point(db, point_id=1, name="КТ3")
    point = map_edit_service.create_point(db, lat=44.53, lon=132.83, stage=1)
    assert point.name == "КТ4"

  def test_update_coordinates(self, db):
    make_idle_game(db)
    point = make_point(db)
    updated = map_edit_service.update_point(db, point.id, lat=44.99, lon=132.11)
    assert updated.lat == 44.99
    assert updated.lon == 132.11

  def test_rejects_when_running(self, db):
    make_point(db)
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
      state = GameState(id=1, status=GameStatus.RUNNING.value)
      db.add(state)
    else:
      state.status = GameStatus.RUNNING.value
    db.commit()
    with pytest.raises(ValueError, match="до старта"):
      map_edit_service.create_point(db, lat=44.53, lon=132.83, stage=1)

  def test_delete_blocked_by_active_hold(self, db):
    make_idle_game(db)
    point = make_point(db)
    db.add(
      HoldSession(
        point_id=point.id,
        side="A",
        started_at=datetime.utcnow(),
        last_ping_at=datetime.utcnow(),
        active=True,
      )
    )
    db.commit()
    with pytest.raises(ValueError, match="активным удержанием"):
      map_edit_service.delete_point(db, point.id)

  def test_create_film_loot_enabled(self, db):
    make_idle_game(db)
    cache = map_edit_service.create_cache(
      db, lat=44.53, lon=132.83, stage=2, cache_kind="film_loot"
    )
    assert cache.enabled is True
    assert cache.name == "Ящик 1"

  def test_create_post_point(self, db):
    make_idle_game(db)
    point = map_edit_service.create_point(db, lat=44.53, lon=132.83, stage=3)
    assert point.name == "Пост-1"

  def test_create_landmark(self, db):
    make_idle_game(db)
    lm = map_edit_service.create_landmark(db, lat=44.53, lon=132.83, kind="base", team_side="A")
    assert lm.team_side == "A"
    assert lm.kind == "base"

  def test_wipe_all_objects(self, db):
    make_idle_game(db)
    make_point(db, point_id=1)
    make_cache(db, cache_id=1)
    map_edit_service.create_landmark(db, lat=44.5, lon=132.5, kind="base", team_side="A")
    n_pts, n_cch, n_lm = map_edit_service.wipe_all_objects(db)
    assert (n_pts, n_cch, n_lm) == (1, 1, 1)
    assert db.query(Point).count() == 0
    assert db.query(Cache).count() == 0
    assert db.query(Landmark).count() == 0

  def test_wipe_rejected_when_running(self, db):
    make_point(db)
    from app.models import GameStatus as GS
    state = db.query(GameState).filter(GameState.id == 1).first()
    if state is None:
      state = GameState(id=1, status=GS.RUNNING.value)
      db.add(state)
    else:
      state.status = GS.RUNNING.value
    db.commit()
    with pytest.raises(ValueError, match="до старта"):
      map_edit_service.wipe_all_objects(db)


class TestMapEditApi:
  def test_create_point_via_api(self, client, db):
    make_idle_game(db)
    admin = make_user(db, user_id=1, username="admin", role="admin", side=None)
    resp = client.post(
      "/api/admin/map/points",
      json={"lat": 44.53, "lon": 132.83, "stage": 1},
      headers=auth_header(admin),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "КТ1"
    assert data["lat"] == 44.53

  def test_patch_point_rejected_when_paused(self, client, db):
    make_point(db)
    state = GameState(id=1, status=GameStatus.PAUSED.value, current_stage=1)
    db.merge(state)
    db.commit()
    admin = make_user(db, user_id=1, username="admin", role="admin", side=None)
    resp = client.patch(
      "/api/admin/map/points/1",
      json={"lat": 44.99},
      headers=auth_header(admin),
    )
    assert resp.status_code == 400

  def test_delete_point_with_hold_via_api(self, client, db):
    make_idle_game(db)
    point = make_point(db)
    db.add(
      HoldSession(
        point_id=point.id,
        side="A",
        started_at=datetime.utcnow(),
        last_ping_at=datetime.utcnow(),
        active=True,
      )
    )
    db.commit()
    admin = make_user(db, user_id=1, username="admin", role="admin", side=None)
    resp = client.delete(f"/api/admin/map/points/{point.id}", headers=auth_header(admin))
    assert resp.status_code == 400
