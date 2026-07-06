import math

from sqlalchemy.orm import Session

from app.models import Landmark

EARTH_RADIUS_M = 6_371_000


ACCURACY_FENCE_BONUS_MAX_M = 20


def effective_fence_radius_m(
  capture_radius: int,
  accuracy: float | None,
  bonus_max_m: int = ACCURACY_FENCE_BONUS_MAX_M,
) -> int:
  bonus = 0
  cap = max(0, int(bonus_max_m))
  if accuracy is not None and accuracy > 0:
    bonus = min(int(accuracy), cap)
  return capture_radius + bonus


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  phi1, phi2 = math.radians(lat1), math.radians(lat2)
  dphi = math.radians(lat2 - lat1)
  dlambda = math.radians(lon2 - lon1)
  a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
  return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_team_base(db: Session, side: str) -> Landmark | None:
  """База стороны для сдачи лута (этап 2)."""
  for kind in ("base_start", "base"):
    base = (
      db.query(Landmark)
      .filter(Landmark.team_side == side, Landmark.kind == kind)
      .first()
    )
    if base:
      return base
  return None
