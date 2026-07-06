from sqlalchemy.orm import Session

from app.models import GameState, MovementTrackPoint
from app.schemas import MovementTrackPointOut, MovementTrackUserOut, MovementTracksResponse
from app.services.game_service import get_or_create_game_state


def current_session_tracks(db: Session) -> MovementTracksResponse:
  game = get_or_create_game_state(db)
  session_id = game.game_session_id or 1
  rows = (
    db.query(MovementTrackPoint)
    .filter(MovementTrackPoint.game_session_id == session_id)
    .order_by(MovementTrackPoint.user_id, MovementTrackPoint.recorded_at, MovementTrackPoint.id)
    .all()
  )

  grouped: dict[int, MovementTrackUserOut] = {}
  for row in rows:
    track = grouped.get(row.user_id)
    point = MovementTrackPointOut(
      lat=row.lat,
      lon=row.lon,
      accuracy=row.accuracy,
      recorded_at=row.recorded_at,
    )
    if track is None:
      grouped[row.user_id] = MovementTrackUserOut(
        user_id=row.user_id,
        username=row.username,
        side=row.side,
        label=row.label,
        points=[point],
      )
    else:
      track.points.append(point)

  tracks = sorted(grouped.values(), key=lambda t: (t.side, t.username))
  return MovementTracksResponse(
    game_session_id=session_id,
    game_status=game.status,
    game_started_at=game.started_at,
    tracks=tracks,
    total_points=len(rows),
  )


def session_track_rows(db: Session, game: GameState) -> list[MovementTrackPoint]:
  session_id = game.game_session_id or 1
  return (
    db.query(MovementTrackPoint)
    .filter(MovementTrackPoint.game_session_id == session_id)
    .order_by(MovementTrackPoint.recorded_at, MovementTrackPoint.id)
    .all()
  )
