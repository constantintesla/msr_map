from app.models import Point

STAGE1_CODE_BASE = 4000


def stage1_point_code(point: Point) -> str:
  if point.detonation_code:
    return point.detonation_code
  return f"{STAGE1_CODE_BASE + point.id:04d}"[-4:]
