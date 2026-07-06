"""Тесты пересчёта очков (on-read)."""

from datetime import datetime, timedelta

from app.models import GameState, GameStatus, HoldSession, Point
from app.services.scoring import (
  FILM_BREACH_BONUS,
  FILM_DELIVER_BONUS,
  HOLD_POINTS_PER_SECOND,
  POINT_CAPTURE_BONUS,
  POST_DESTROY_BONUS,
  calculate_score_breakdown,
  calculate_scores,
)
from tests.conftest import make_point, make_running_game


def _add_hold_session(
  db,
  *,
  point_id: int,
  side: str,
  started_at: datetime,
  ended_at: datetime | None = None,
  active: bool = False,
  hold_ready: bool = False,
) -> HoldSession:
  session = HoldSession(
    point_id=point_id,
    side=side,
    started_at=started_at,
    ended_at=ended_at,
    last_ping_at=ended_at or started_at,
    active=active,
    hold_ready=hold_ready,
  )
  db.add(session)
  db.commit()
  return session


class TestCalculateScores:
  def test_post_destroy_bonus_1000_both_sides(self, db):
    make_running_game(db, stage=3)
    make_point(db, point_id=1, stage=3, name="Пост-1")
    make_point(db, point_id=2, stage=3, name="Пост-2")
    p1 = db.query(Point).filter(Point.id == 1).first()
    p2 = db.query(Point).filter(Point.id == 2).first()
    p1.destroyed = True
    p1.destroyed_by_side = "A"
    p2.destroyed = True
    p2.destroyed_by_side = "B"
    db.commit()

    game = db.query(GameState).filter(GameState.id == 1).first()
    score_a, score_b = calculate_scores(db, game)

    assert score_a == POST_DESTROY_BONUS == 1000
    assert score_b == POST_DESTROY_BONUS == 1000

  def test_stage2_point_hold_not_counted(self, db):
    game = make_running_game(db, stage=1)
    started = game.started_at or datetime.utcnow()
    make_point(db, point_id=10, stage=2, name="КТ-этап2")
    _add_hold_session(
      db,
      point_id=10,
      side="A",
      started_at=started,
      ended_at=started + timedelta(minutes=10),
      active=False,
    )

    score_a, score_b = calculate_scores(db, game)

    assert score_a == 0
    assert score_b == 0

  def test_hold_rate_low(self, db):
    game = make_running_game(db, stage=1)
    started = game.started_at or datetime.utcnow()
    point = make_point(db, point_id=1, stage=1, name="KT1")
    point.coefficient = 1.0
    db.commit()
    _add_hold_session(
      db,
      point_id=1,
      side="A",
      started_at=started,
      ended_at=started + timedelta(seconds=100),
      active=False,
    )

    score_a, score_b = calculate_scores(db, game)

    assert score_a == int(100 * HOLD_POINTS_PER_SECOND)
    assert score_b == 0

  def test_capture_bonus(self, db):
    game = make_running_game(db, stage=1)
    started = game.started_at or datetime.utcnow()
    point = make_point(db, point_id=1, stage=1, name="KT1")
    point.coefficient = 1.0
    db.commit()
    _add_hold_session(
      db,
      point_id=1,
      side="A",
      started_at=started,
      ended_at=started + timedelta(seconds=120),
      active=False,
      hold_ready=True,
    )

    bd = calculate_score_breakdown(db, game)

    assert bd.side_a.hold == int(120 * HOLD_POINTS_PER_SECOND)
    assert bd.side_a.captures == POINT_CAPTURE_BONUS
    assert bd.score_a == bd.side_a.hold + POINT_CAPTURE_BONUS

  def test_recapture_both_sides(self, db):
    game = make_running_game(db, stage=1)
    started = game.started_at or datetime.utcnow()
    make_point(db, point_id=1, stage=1, name="KT1")
    _add_hold_session(
      db,
      point_id=1,
      side="A",
      started_at=started,
      ended_at=started + timedelta(seconds=120),
      active=False,
      hold_ready=True,
    )
    _add_hold_session(
      db,
      point_id=1,
      side="B",
      started_at=started + timedelta(minutes=5),
      ended_at=started + timedelta(minutes=7),
      active=False,
      hold_ready=True,
    )

    bd = calculate_score_breakdown(db, game)

    assert bd.side_a.captures == POINT_CAPTURE_BONUS
    assert bd.side_b.captures == POINT_CAPTURE_BONUS

  def test_delivery_total_650(self, db):
    from tests.conftest import make_cache

    make_running_game(db, stage=2)
    cache = make_cache(db, cache_id=1)
    cache.destroyed = True
    cache.destroyed_by_side = "A"
    cache.destroyed_at = datetime.utcnow()
    cache.delivered_at = datetime.utcnow()
    cache.delivered_by_side = "A"
    db.commit()

    game = db.query(GameState).filter(GameState.id == 1).first()
    score_a, _ = calculate_scores(db, game)

    assert score_a == FILM_BREACH_BONUS + FILM_DELIVER_BONUS == 650

  def test_film_breach_bonus_unchanged(self, db):
    from tests.conftest import make_cache

    make_running_game(db, stage=2)
    cache = make_cache(db, cache_id=1)
    cache.destroyed = True
    cache.destroyed_by_side = "B"
    cache.destroyed_at = datetime.utcnow()
    db.commit()

    game = db.query(GameState).filter(GameState.id == 1).first()
    _, score_b = calculate_scores(db, game)

    assert score_b == FILM_BREACH_BONUS

  def test_pause_freezes_active_hold(self, db):
    game = make_running_game(db, stage=1)
    started = game.started_at or datetime.utcnow()
    make_point(db, point_id=1, stage=1, name="KT1")
    _add_hold_session(
      db,
      point_id=1,
      side="A",
      started_at=started,
      active=True,
    )

    game.status = GameStatus.PAUSED.value
    db.commit()

    score_a, _ = calculate_scores(db, game)
    assert score_a == 0

    ended = db.query(HoldSession).first()
    ended.active = False
    ended.ended_at = started + timedelta(seconds=200)
    ended.hold_ready = True
    db.commit()

    score_a, _ = calculate_scores(db, game)
    assert score_a == int(200 * HOLD_POINTS_PER_SECOND) + POINT_CAPTURE_BONUS

  def test_no_scores_when_game_idle(self, db):
    make_point(db, point_id=1, stage=1)
    game = GameState(id=1, status=GameStatus.IDLE.value)
    db.add(game)
    db.commit()

    score_a, score_b = calculate_scores(db, game)

    assert score_a == 0
    assert score_b == 0
