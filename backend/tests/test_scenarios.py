"""Тесты мульти-сценариев: создание, активация, изоляция данных между сценариями."""

from app.models import Point
from app.services import map_edit_service
from app.services.scenario_service import activate_scenario, create_scenario, get_active_scenario_id
from tests.conftest import auth_header, make_point, make_running_game, make_user


def _admin(db):
  return make_user(db, user_id=99, username="admin", role="admin", side=None)


class TestScenarioCrudApi:
  def test_create_scenario_not_active(self, client, db):
    admin = _admin(db)
    resp = client.post(
      "/api/admin/scenarios", json={"name": "Мероприятие 2"}, headers=auth_header(admin)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Мероприятие 2"
    assert data["is_active"] is False

  def test_list_scenarios_includes_default(self, client, db):
    admin = _admin(db)
    get_active_scenario_id(db)  # бутстрап дефолтного сценария
    resp = client.get("/api/admin/scenarios", headers=auth_header(admin))
    assert resp.status_code == 200
    names = [s["name"] for s in resp.json()]
    assert "Мероприятие 1" in names

  def test_activate_scenario_flips_flag(self, client, db):
    admin = _admin(db)
    get_active_scenario_id(db)
    created = client.post(
      "/api/admin/scenarios", json={"name": "Второе"}, headers=auth_header(admin)
    ).json()

    resp = client.post(f"/api/admin/scenarios/{created['id']}/activate", headers=auth_header(admin))
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    scenarios = {s["id"]: s for s in client.get("/api/admin/scenarios", headers=auth_header(admin)).json()}
    assert scenarios[created["id"]]["is_active"] is True
    other = [s for sid, s in scenarios.items() if sid != created["id"]]
    assert all(not s["is_active"] for s in other)

  def test_cannot_archive_active_scenario(self, client, db):
    admin = _admin(db)
    scenario_id = get_active_scenario_id(db)
    resp = client.post(f"/api/admin/scenarios/{scenario_id}/archive", headers=auth_header(admin))
    assert resp.status_code == 400


class TestScenarioIsolation:
  def test_new_scenario_has_no_points(self, db):
    get_active_scenario_id(db)  # бутстрап сценария 1, чтобы "Событие 2" не унаследовало id=1
    make_point(db, point_id=1)
    scenario2 = create_scenario(db, "Событие 2")
    activate_scenario(db, scenario2.id)

    points_in_scenario2 = db.query(Point).filter(Point.scenario_id == scenario2.id).all()
    assert points_in_scenario2 == []

    # первый сценарий не пострадал
    original = db.query(Point).filter(Point.scenario_id == 1).all()
    assert len(original) == 1

  def test_map_edit_create_point_scopes_to_active_scenario(self, db):
    make_running_game(db)  # создаёт GameState(id=1) -> сценарий 1 неявно активен
    scenario2 = create_scenario(db, "Событие 2")
    activate_scenario(db, scenario2.id)

    point = map_edit_service.create_point(db, lat=1.0, lon=2.0, stage=1)
    assert point.scenario_id == scenario2.id

  def test_reset_game_does_not_touch_other_scenario(self, db):
    from app.services.game_service import reset_game

    make_running_game(db, stage=1)
    pt1 = make_point(db, point_id=1, side="A")

    scenario2 = create_scenario(db, "Событие 2")
    activate_scenario(db, scenario2.id)

    reset_game(db)  # действует только на активный (scenario2), не должен трогать scenario1

    db.refresh(pt1)
    assert pt1.side == "A"

  def test_status_response_only_shows_active_scenario_points(self, client, db):
    admin = _admin(db)
    make_running_game(db, stage=1)
    make_point(db, point_id=1, name="КТ активного сценария")

    scenario2 = create_scenario(db, "Событие 2")
    activate_scenario(db, scenario2.id)

    resp = client.get("/api/admin/status", headers=auth_header(admin))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["points"]]
    assert "КТ активного сценария" not in names
