from datetime import datetime

from app.models import GameState, GameStatus, MovementTrackPoint
from app.services.game_service import get_or_create_game_state, reset_game, start_game
from app.services.movement_track_service import current_session_tracks
from tests.conftest import auth_header, make_running_game, make_user


def test_location_ping_records_track_when_game_running(client, db):
  make_running_game(db, stage=1)
  eng = make_user(db, username="eng_a1", side="A")
  state = db.query(GameState).filter_by(id=1).first()
  state.game_session_id = 7
  db.commit()

  res = client.post(
    "/api/location/ping",
    json={"lat": 44.52, "lon": 132.82, "accuracy": 5},
    headers=auth_header(eng),
  )
  assert res.status_code == 200

  row = (
    db.query(MovementTrackPoint)
    .filter(MovementTrackPoint.user_id == eng.id, MovementTrackPoint.game_session_id == 7)
    .first()
  )
  assert row is not None
  assert row.lat == 44.52
  assert row.lon == 132.82


def test_location_ping_skips_track_when_game_idle(client, db):
  eng = make_user(db, username="eng_a1", side="A")
  state = get_or_create_game_state(db)
  state.status = GameStatus.IDLE.value
  state.started_at = None
  state.game_session_id = 3
  db.commit()

  res = client.post(
    "/api/location/ping",
    json={"lat": 44.5, "lon": 132.8, "accuracy": 5},
    headers=auth_header(eng),
  )
  assert res.status_code == 200
  assert db.query(MovementTrackPoint).filter(MovementTrackPoint.game_session_id == 3).count() == 0


def test_reset_increments_game_session_id(db):
  state = get_or_create_game_state(db)
  state.game_session_id = 4
  db.commit()

  reset_game(db)
  db.refresh(state)
  assert state.game_session_id == 5


def test_admin_movement_tracks_api(client, db):
  admin = make_user(db, user_id=99, username="admin_user", role="admin", side=None)
  eng = make_user(db, user_id=2, username="eng_b1", side="B")
  make_running_game(db, stage=1)
  state = get_or_create_game_state(db)
  session_id = state.game_session_id or 1

  db.add(
    MovementTrackPoint(
      game_session_id=session_id,
      user_id=eng.id,
      username=eng.username,
      side=eng.side,
      label=eng.username,
      lat=44.51,
      lon=132.81,
      accuracy=4,
      recorded_at=datetime.utcnow(),
    )
  )
  db.commit()

  res = client.get("/api/admin/movement-tracks", headers=auth_header(admin))
  assert res.status_code == 200
  data = res.json()
  assert data["game_session_id"] == session_id
  assert data["total_points"] == 1
  assert len(data["tracks"]) == 1
  assert data["tracks"][0]["user_id"] == eng.id

  tracks = current_session_tracks(db)
  assert tracks.total_points == 1
