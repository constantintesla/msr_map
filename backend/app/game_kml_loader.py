from pathlib import Path

from sqlalchemy.orm import Session

from app.kmz_parser import ParsedCache, ParsedLandmark, ParsedPoint, load_preset_game_kml
from app.models import Cache, HoldSession, Landmark, Point
from app.services.game_service import log_event


def apply_game_objects(
  db: Session,
  points: list[ParsedPoint],
  caches: list[ParsedCache],
  landmarks: list[ParsedLandmark] | None = None,
  *,
  source: str = "kml",
) -> tuple[int, int, int]:
  """Полная перезапись точек, схронов и ориентиров в БД."""
  landmarks = landmarks or []

  db.query(HoldSession).delete()
  db.query(Point).delete()
  db.query(Cache).delete()
  db.query(Landmark).delete()
  db.flush()

  for i, p in enumerate(points, start=1):
    db.add(
      Point(
        id=i,
        name=p.name,
        lat=p.lat,
        lon=p.lon,
        coefficient=1.0,
        side=None,
        stage=p.stage,
        detonation_code=f"{3000 + i:04d}"[-4:] if p.stage == 3 else (f"{4000 + i:04d}"[-4:] if p.stage == 1 else None),
      )
    )

  for i, c in enumerate(caches, start=1):
    code = f"{2000 + i:04d}"[-4:] if c.cache_kind == "film_loot" else f"{1000 + i:04d}"[-4:]
    db.add(
      Cache(
        id=i,
        name=c.name,
        lat=c.lat,
        lon=c.lon,
        team_side=c.team_side,
        stage=c.stage,
        cache_kind=c.cache_kind or "post",
        detonation_code=code,
        enabled=c.cache_kind not in ("mertvyak", "film_loot"),
        loot_variant=getattr(c, "loot_variant", None) or "film_passage",
      )
    )

  for i, lm in enumerate(landmarks, start=1):
    db.add(
      Landmark(
        id=i,
        name=lm.name,
        lat=lm.lat,
        lon=lm.lon,
        kind=lm.kind,
        team_side=lm.team_side,
      )
    )

  log_event(
    db,
    "kml_import",
    {
      "source": source,
      "points": len(points),
      "caches": len(caches),
      "landmarks": len(landmarks),
      "caches_a": sum(1 for c in caches if c.team_side == "A"),
      "caches_b": sum(1 for c in caches if c.team_side == "B"),
    },
  )
  db.commit()
  from app.qr_tokens import ensure_cache_qr_token, ensure_point_qr_token

  for point in db.query(Point).all():
    if not point.qr_token:
      ensure_point_qr_token(point, db)
  for cache in db.query(Cache).all():
    if not cache.qr_token:
      ensure_cache_qr_token(cache, db)
  db.commit()
  return len(points), len(caches), len(landmarks)


def load_kmz_dir_into_db(db: Session, kmz_dir: Path) -> tuple[int, int, int] | None:
  from app.stage2_loot import ensure_stage2_loot_caches

  points, caches, landmarks = load_preset_game_kml(kmz_dir)
  if not points and not caches and not landmarks:
    return None
  result = apply_game_objects(db, points, caches, landmarks, source=str(kmz_dir))
  ensure_stage2_loot_caches(db)
  pts = db.query(Point).count()
  cchs = db.query(Cache).count()
  lms = db.query(Landmark).count()
  return pts, cchs, lms
