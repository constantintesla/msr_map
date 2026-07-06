"""Генерация 10 ящиков этапа 2, если нет Задача-2.kml."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Cache, Point


def ensure_stage2_loot_caches(db: Session) -> int:
  """10 нейтральных ящиков за плёнкой вокруг зоны этапа 1."""
  if db.query(Cache).filter(Cache.stage == 2).count() >= 10:
    return db.query(Cache).filter(Cache.stage == 2).count()

  ref = db.query(Point).filter(Point.stage == 1).order_by(Point.id).first()
  base_lat = ref.lat if ref else 44.526
  base_lon = ref.lon if ref else 132.827

  next_id = (db.query(func.max(Cache.id)).scalar() or 0) + 1
  created = 0

  for i in range(1, 11):
    if db.query(Cache).filter(Cache.stage == 2, Cache.name == f"Ящик {i}").first():
      continue
    db.add(
      Cache(
        id=next_id,
        name=f"Ящик {i}",
        lat=base_lat + ((i % 5) - 2) * 0.0008,
        lon=base_lon + ((i % 4) - 1) * 0.0012,
        stage=2,
        cache_kind="film_loot",
        team_side=None,
        detonation_code=f"{2000 + i:04d}"[-4:],
        loot_variant="film_passage",
      )
    )
    next_id += 1
    created += 1

  if created:
    db.commit()
  return db.query(Cache).filter(Cache.stage == 2).count()
