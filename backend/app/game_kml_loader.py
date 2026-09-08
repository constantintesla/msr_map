from pathlib import Path

from sqlalchemy.orm import Session

from app.kmz_parser import ParsedCache, ParsedLandmark, ParsedPoint, load_preset_game_kml
from app.models import (
  Cache,
  CacheHoldSession,
  FieldOrder,
  HoldSession,
  Landmark,
  Point,
  PointReconPhoto,
  Stage2Assignment,
  User,
)
from app.services.game_service import log_event


def apply_game_objects(
  db: Session,
  points: list[ParsedPoint],
  caches: list[ParsedCache],
  landmarks: list[ParsedLandmark] | None = None,
  *,
  scenario_id: int,
  source: str = "kml",
) -> tuple[int, int, int]:
  """Полная перезапись точек, схронов и ориентиров данного сценария в БД."""
  landmarks = landmarks or []

  stale_point_ids = [
    p.id for p in db.query(Point.id).filter(Point.scenario_id == scenario_id).all()
  ]
  stale_cache_ids = [
    c.id for c in db.query(Cache.id).filter(Cache.scenario_id == scenario_id).all()
  ]

  db.query(PointReconPhoto).filter(PointReconPhoto.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(HoldSession).filter(HoldSession.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(CacheHoldSession).filter(CacheHoldSession.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(Stage2Assignment).filter(Stage2Assignment.scenario_id == scenario_id).delete(
    synchronize_session=False
  )
  db.query(FieldOrder).filter(
    FieldOrder.scenario_id == scenario_id, FieldOrder.target_kind.in_(("point", "cache"))
  ).delete(synchronize_session=False)
  if stale_point_ids:
    db.query(User).filter(User.point_id.in_(stale_point_ids)).update(
      {User.point_id: None}, synchronize_session=False
    )
  if stale_cache_ids:
    db.query(User).filter(User.cache_id.in_(stale_cache_ids)).update(
      {User.cache_id: None}, synchronize_session=False
    )
  db.query(Point).filter(Point.scenario_id == scenario_id).delete(synchronize_session=False)
  db.query(Cache).filter(Cache.scenario_id == scenario_id).delete(synchronize_session=False)
  db.query(Landmark).filter(Landmark.scenario_id == scenario_id).delete(synchronize_session=False)
  db.flush()

  for i, p in enumerate(points, start=1):
    db.add(
      Point(
        scenario_id=scenario_id,
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
        scenario_id=scenario_id,
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

  for lm in landmarks:
    db.add(
      Landmark(
        scenario_id=scenario_id,
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

  for point in db.query(Point).filter(Point.scenario_id == scenario_id).all():
    if not point.qr_token:
      ensure_point_qr_token(point, db)
  for cache in db.query(Cache).filter(Cache.scenario_id == scenario_id).all():
    if not cache.qr_token:
      ensure_cache_qr_token(cache, db)
  db.commit()
  return len(points), len(caches), len(landmarks)


def load_kmz_dir_into_db(db: Session, kmz_dir: Path, scenario_id: int) -> tuple[int, int, int] | None:
  from app.stage2_loot import ensure_stage2_loot_caches

  points, caches, landmarks = load_preset_game_kml(kmz_dir)
  if not points and not caches and not landmarks:
    return None
  apply_game_objects(db, points, caches, landmarks, scenario_id=scenario_id, source=str(kmz_dir))
  ensure_stage2_loot_caches(db, scenario_id)
  pts = db.query(Point).filter(Point.scenario_id == scenario_id).count()
  cchs = db.query(Cache).filter(Cache.scenario_id == scenario_id).count()
  lms = db.query(Landmark).filter(Landmark.scenario_id == scenario_id).count()
  return pts, cchs, lms
