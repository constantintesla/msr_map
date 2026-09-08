from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Cache, GameState, GameStatus, HoldSession, Point

HOLD_POINTS_PER_SECOND = 0.05
POINT_CAPTURE_BONUS = 100
CACHE_DESTROY_BONUS = 500
POST_DESTROY_BONUS = 1000
FILM_BREACH_BONUS = 150
FILM_DELIVER_BONUS = 500


@dataclass
class SideBreakdown:
  hold: int = 0
  captures: int = 0
  loot_breach: int = 0
  loot_deliver: int = 0
  posts: int = 0
  caches: int = 0

  @property
  def total(self) -> int:
    return self.hold + self.captures + self.loot_breach + self.loot_deliver + self.posts + self.caches


@dataclass
class ScoreBreakdown:
  side_a: SideBreakdown = field(default_factory=SideBreakdown)
  side_b: SideBreakdown = field(default_factory=SideBreakdown)

  @property
  def score_a(self) -> int:
    return self.side_a.total

  @property
  def score_b(self) -> int:
    return self.side_b.total


def _side_breakdown(bd: ScoreBreakdown, side: str) -> SideBreakdown:
  return bd.side_a if side == "A" else bd.side_b


def _scoring_active(game: GameState) -> bool:
  return bool(game.started_at) and game.status in (GameStatus.RUNNING.value, GameStatus.PAUSED.value)


def _hold_elapsed_seconds(
  session: HoldSession,
  game: GameState,
  now: datetime,
) -> float:
  if not game.started_at:
    return 0.0
  start = max(session.started_at, game.started_at)
  if session.active and session.last_ping_at:
    if game.status != GameStatus.RUNNING.value:
      return 0.0
    return max(0.0, (now - start).total_seconds())
  if session.ended_at:
    return max(0.0, (session.ended_at - start).total_seconds())
  return 0.0


def calculate_score_breakdown(db: Session, game: GameState) -> ScoreBreakdown:
  """Баллы on-read: без cron, пересчёт при каждом запросе статуса."""
  bd = ScoreBreakdown()
  if not _scoring_active(game):
    return bd

  now = datetime.utcnow()
  scenario_id = game.id
  points = {
    p.id: p
    for p in db.query(Point).filter(Point.scenario_id == scenario_id, Point.stage != 2).all()
  }

  for session in db.query(HoldSession).filter(HoldSession.scenario_id == scenario_id).all():
    point = points.get(session.point_id)
    if point is None:
      continue
    coef = point.coefficient or 1.0
    elapsed = _hold_elapsed_seconds(session, game, now)
    hold_pts = int(elapsed * HOLD_POINTS_PER_SECOND * coef)
    side_bd = _side_breakdown(bd, session.side)
    side_bd.hold += hold_pts

    if point.stage == 1 and session.hold_ready and session.ended_at:
      side_bd.captures += int(POINT_CAPTURE_BONUS * coef)

  for cache in db.query(Cache).filter(Cache.scenario_id == scenario_id, Cache.destroyed.is_(True)).all():
    if cache.cache_kind == "film_loot":
      if cache.delivered_at:
        side = cache.delivered_by_side
        if side in ("A", "B"):
          side_bd = _side_breakdown(bd, side)
          side_bd.loot_breach += FILM_BREACH_BONUS
          side_bd.loot_deliver += FILM_DELIVER_BONUS
      elif cache.destroyed_by_side in ("A", "B"):
        _side_breakdown(bd, cache.destroyed_by_side).loot_breach += FILM_BREACH_BONUS
    elif cache.destroyed_by_side in ("A", "B"):
      _side_breakdown(bd, cache.destroyed_by_side).caches += CACHE_DESTROY_BONUS

  for post in (
    db.query(Point)
    .filter(Point.scenario_id == scenario_id, Point.destroyed.is_(True), Point.stage == 3)
    .all()
  ):
    if post.destroyed_by_side in ("A", "B"):
      _side_breakdown(bd, post.destroyed_by_side).posts += POST_DESTROY_BONUS

  return bd


def calculate_scores(db: Session, game: GameState) -> tuple[int, int]:
  breakdown = calculate_score_breakdown(db, game)
  return breakdown.score_a, breakdown.score_b
