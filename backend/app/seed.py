from pathlib import Path

from app.auth import hash_password
from app.database import SessionLocal
from app.game_kml_loader import load_kmz_dir_into_db
from app.stage2_loot import ensure_stage2_loot_caches
from app.models import Cache, GameState, Point, Scenario, User
from app.services.engineer_pool_service import sync_engineer_pool
from app.services.scenario_service import DEFAULT_SCENARIO_NAME, DEFAULT_SCENARIO_SLUG

# Каталог с KML пресета игры (от корня репозитория)
KMZ_DIR = Path(__file__).resolve().parents[2] / "kmz"


def _ensure_demo_users(db) -> None:
  """Админ, командиры и пул инженеров по настройкам game_state."""
  if db.query(User).filter(User.username == "admin").first() is None:
    db.add(
      User(
        username="admin",
        password_hash=hash_password("admin"),
        role="admin",
      )
    )

  for side, password, username in [("A", "alfa", "cmd_a"), ("B", "bravo", "cmd_b")]:
    if db.query(User).filter(User.username == username).first():
      continue
    db.add(
      User(
        username=username,
        password_hash=hash_password(password),
        role="commander",
        side=side,
      )
    )

  sync_engineer_pool(db, purge_legacy=True)


def _seed_fallback_moscow(db, scenario_id: int) -> None:
  """Запасные координаты, если kmz/ пуст."""
  if db.query(Point).filter(Point.scenario_id == scenario_id).count() > 0:
    return
  base_lat, base_lon = 56.1200, 37.2500
  for i in range(1, 8):
    db.add(
      Point(
        scenario_id=scenario_id,
        name=f"Точка {i}",
        lat=base_lat + i * 0.002,
        lon=base_lon + i * 0.001,
        coefficient=1.0,
        stage=1,
        detonation_code=f"{4000 + i:04d}"[-4:],
      )
    )
  for i in range(1, 11):
    db.add(
      Cache(
        scenario_id=scenario_id,
        name=f"Схрон {i}",
        lat=base_lat - i * 0.0015,
        lon=base_lon + i * 0.002,
        team_side="A" if i % 2 else "B",
        stage=3,
        cache_kind="post",
        detonation_code=f"{1000 + i:04d}"[-4:],
      )
    )


def _ensure_default_scenario(db) -> Scenario:
  scenario = db.query(Scenario).filter(Scenario.is_active.is_(True)).first()
  if scenario is not None:
    return scenario
  scenario = db.query(Scenario).order_by(Scenario.id).first()
  if scenario is None:
    scenario = Scenario(name=DEFAULT_SCENARIO_NAME, slug=DEFAULT_SCENARIO_SLUG, is_active=True)
    db.add(scenario)
    db.flush()
  else:
    scenario.is_active = True
  return scenario


def seed_database() -> None:
  db = SessionLocal()
  try:
    scenario = _ensure_default_scenario(db)
    db.commit()

    # KML из kmz/ — только при пустом активном сценарии; иначе POST /api/admin/kml/reload
    if db.query(Point).filter(Point.scenario_id == scenario.id).count() == 0:
      result = load_kmz_dir_into_db(db, KMZ_DIR, scenario.id)
      if result is None:
        _seed_fallback_moscow(db, scenario.id)
        db.commit()

    ensure_stage2_loot_caches(db, scenario.id)

    if db.query(GameState).filter(GameState.id == scenario.id).first() is None:
      db.add(GameState(id=scenario.id))

    db.commit()
    _ensure_demo_users(db)

    db.commit()
  finally:
    db.close()
