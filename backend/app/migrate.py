from sqlalchemy import inspect, text

from app.database import engine

_IS_SQLITE = engine.dialect.name == "sqlite"
_DATETIME = "DATETIME" if _IS_SQLITE else "TIMESTAMP"


def _bool_default(value: bool) -> str:
  if _IS_SQLITE:
    return "1" if value else "0"
  return "TRUE" if value else "FALSE"


def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
  insp = inspect(engine)
  if not insp.has_table(table):
    return
  cols = {c["name"] for c in insp.get_columns(table)}
  if column not in cols:
    with engine.begin() as conn:
      conn.execute(text(ddl))


def run_migrations() -> None:
  """Лёгкие миграции SQLite без Alembic."""
  _add_column_if_missing("caches", "team_side", "ALTER TABLE caches ADD COLUMN team_side VARCHAR(1)")
  _add_column_if_missing("caches", "stage", "ALTER TABLE caches ADD COLUMN stage INTEGER DEFAULT 3")
  _add_column_if_missing("points", "stage", "ALTER TABLE points ADD COLUMN stage INTEGER DEFAULT 1")
  _add_column_if_missing("caches", "cache_kind", "ALTER TABLE caches ADD COLUMN cache_kind VARCHAR(16) DEFAULT 'post'")
  _add_column_if_missing(
    "caches",
    "delivery_reported_at",
    f"ALTER TABLE caches ADD COLUMN delivery_reported_at {_DATETIME}",
  )
  _add_column_if_missing("caches", "delivered_at", f"ALTER TABLE caches ADD COLUMN delivered_at {_DATETIME}")
  _add_column_if_missing("caches", "delivered_by_side", "ALTER TABLE caches ADD COLUMN delivered_by_side VARCHAR(1)")
  _add_column_if_missing("game_state", "current_stage", "ALTER TABLE game_state ADD COLUMN current_stage INTEGER DEFAULT 1")
  _add_column_if_missing(
    "caches",
    "admin_confirmed",
    f"ALTER TABLE caches ADD COLUMN admin_confirmed BOOLEAN DEFAULT {_bool_default(False)}",
  )
  _add_column_if_missing(
    "caches",
    "enabled",
    f"ALTER TABLE caches ADD COLUMN enabled BOOLEAN DEFAULT {_bool_default(True)}",
  )
  _add_column_if_missing("points", "detonation_code", "ALTER TABLE points ADD COLUMN detonation_code VARCHAR(6)")
  _add_column_if_missing(
    "points",
    "destroyed",
    f"ALTER TABLE points ADD COLUMN destroyed BOOLEAN DEFAULT {_bool_default(False)}",
  )
  _add_column_if_missing("points", "destroyed_at", f"ALTER TABLE points ADD COLUMN destroyed_at {_DATETIME}")
  _add_column_if_missing("points", "destroyed_by_side", "ALTER TABLE points ADD COLUMN destroyed_by_side VARCHAR(1)")
  _add_column_if_missing(
    "points",
    "enabled",
    f"ALTER TABLE points ADD COLUMN enabled BOOLEAN DEFAULT {_bool_default(True)}",
  )
  _add_column_if_missing(
    "landmarks",
    "enabled",
    f"ALTER TABLE landmarks ADD COLUMN enabled BOOLEAN DEFAULT {_bool_default(True)}",
  )
  _add_column_if_missing(
    "hold_sessions",
    "hold_ready",
    f"ALTER TABLE hold_sessions ADD COLUMN hold_ready BOOLEAN DEFAULT {_bool_default(False)}",
  )
  _add_column_if_missing("hold_sessions", "user_id", "ALTER TABLE hold_sessions ADD COLUMN user_id INTEGER")
  _add_column_if_missing("chat_messages", "thread", "ALTER TABLE chat_messages ADD COLUMN thread VARCHAR(8) DEFAULT 'cmd'")
  _add_column_if_missing("chat_messages", "recipient_username", "ALTER TABLE chat_messages ADD COLUMN recipient_username VARCHAR(64)")
  _add_column_if_missing("users", "lpd_channel", "ALTER TABLE users ADD COLUMN lpd_channel INTEGER")
  _add_column_if_missing("users", "password_plain", "ALTER TABLE users ADD COLUMN password_plain VARCHAR(16)")
  _add_column_if_missing("game_state", "game_session_id", "ALTER TABLE game_state ADD COLUMN game_session_id INTEGER DEFAULT 1")
  _add_column_if_missing("game_state", "engineers_per_side_a", "ALTER TABLE game_state ADD COLUMN engineers_per_side_a INTEGER DEFAULT 5")
  _add_column_if_missing("game_state", "engineers_per_side_b", "ALTER TABLE game_state ADD COLUMN engineers_per_side_b INTEGER DEFAULT 5")
  _add_column_if_missing("game_state", "capture_radius_m", "ALTER TABLE game_state ADD COLUMN capture_radius_m INTEGER DEFAULT 15")
  _add_column_if_missing(
    "game_state",
    "disable_capture_distance",
    f"ALTER TABLE game_state ADD COLUMN disable_capture_distance BOOLEAN DEFAULT {_bool_default(False)}",
  )
  _add_column_if_missing(
    "game_state",
    "stage1_recapturable",
    f"ALTER TABLE game_state ADD COLUMN stage1_recapturable BOOLEAN DEFAULT {_bool_default(True)}",
  )
  _add_column_if_missing("game_state", "point_capture_seconds", "ALTER TABLE game_state ADD COLUMN point_capture_seconds INTEGER DEFAULT 120")
  _add_column_if_missing("game_state", "point_hold_ping_seconds", "ALTER TABLE game_state ADD COLUMN point_hold_ping_seconds INTEGER DEFAULT 120")
  _add_column_if_missing("game_state", "post_hold_seconds", "ALTER TABLE game_state ADD COLUMN post_hold_seconds INTEGER DEFAULT 600")
  _add_column_if_missing("game_state", "post_hold_ping_seconds", "ALTER TABLE game_state ADD COLUMN post_hold_ping_seconds INTEGER DEFAULT 120")
  _add_column_if_missing("game_state", "stage2_issue_interval_minutes", "ALTER TABLE game_state ADD COLUMN stage2_issue_interval_minutes INTEGER DEFAULT 60")
  _add_column_if_missing("game_state", "stage2_issue_mode", "ALTER TABLE game_state ADD COLUMN stage2_issue_mode VARCHAR(16) DEFAULT 'random'")
  _add_column_if_missing(
    "game_state",
    "stage2_last_issued_at",
    f"ALTER TABLE game_state ADD COLUMN stage2_last_issued_at {_DATETIME}",
  )
  _add_column_if_missing("game_state", "stage2_sequential_index", "ALTER TABLE game_state ADD COLUMN stage2_sequential_index INTEGER DEFAULT 0")
  _add_column_if_missing("game_state", "stage1_recon_minutes", "ALTER TABLE game_state ADD COLUMN stage1_recon_minutes INTEGER DEFAULT 120")
  _add_column_if_missing("game_state", "stage1_slot_minutes", "ALTER TABLE game_state ADD COLUMN stage1_slot_minutes INTEGER DEFAULT 120")
  _add_column_if_missing("game_state", "stage1_hold_slots_json", "ALTER TABLE game_state ADD COLUMN stage1_hold_slots_json TEXT")
  _add_column_if_missing("game_state", "stage1_current_slot", "ALTER TABLE game_state ADD COLUMN stage1_current_slot INTEGER DEFAULT -1")
  _add_column_if_missing(
    "game_state",
    "stage1_slots_started_at",
    f"ALTER TABLE game_state ADD COLUMN stage1_slots_started_at {_DATETIME}",
  )
  _add_column_if_missing(
    "game_state",
    "stage2_enabled",
    f"ALTER TABLE game_state ADD COLUMN stage2_enabled BOOLEAN DEFAULT {_bool_default(False)}",
  )
  _add_column_if_missing(
    "game_state",
    "stage2_start_at",
    f"ALTER TABLE game_state ADD COLUMN stage2_start_at {_DATETIME}",
  )
  _add_column_if_missing("game_state", "gps_accuracy_bonus_max_m", "ALTER TABLE game_state ADD COLUMN gps_accuracy_bonus_max_m INTEGER DEFAULT 20")
  _add_column_if_missing("game_state", "gps_min_accuracy_for_capture_m", "ALTER TABLE game_state ADD COLUMN gps_min_accuracy_for_capture_m INTEGER DEFAULT 0")
  _add_column_if_missing("game_state", "gps_lat_offset", "ALTER TABLE game_state ADD COLUMN gps_lat_offset REAL DEFAULT 0")
  _add_column_if_missing("game_state", "gps_lon_offset", "ALTER TABLE game_state ADD COLUMN gps_lon_offset REAL DEFAULT 0")
  _add_column_if_missing("caches", "loot_variant", "ALTER TABLE caches ADD COLUMN loot_variant VARCHAR(16) DEFAULT 'film_passage'")
  _add_column_if_missing(
    "caches",
    "code_verified_at",
    f"ALTER TABLE caches ADD COLUMN code_verified_at {_DATETIME}",
  )
  _add_column_if_missing("caches", "code_verified_by_side", "ALTER TABLE caches ADD COLUMN code_verified_by_side VARCHAR(1)")
  _add_column_if_missing("points", "qr_token", "ALTER TABLE points ADD COLUMN qr_token VARCHAR(24)")
  _add_column_if_missing("caches", "qr_token", "ALTER TABLE caches ADD COLUMN qr_token VARCHAR(24)")
  _add_column_if_missing("caches", "code_verified_qr_token", "ALTER TABLE caches ADD COLUMN code_verified_qr_token VARCHAR(24)")
  _backfill_engineer_passwords()
  _ensure_demo_engineer_passwords()
  _backfill_stage1_point_codes()
  _backfill_loot_variant()
  _backfill_qr_tokens()


def _ensure_demo_engineer_passwords() -> None:
  from app.auth import hash_password
  from app.database import SessionLocal
  from app.models import User
  from app.services.engineer_pool_service import DEMO_ENGINEER_PASSWORD

  db = SessionLocal()
  try:
    changed = False
    for username, side in [("eng_a1", "A"), ("eng_b1", "B")]:
      user = db.query(User).filter(User.username == username, User.role == "engineer").first()
      if user is None:
        continue
      password = DEMO_ENGINEER_PASSWORD[side]
      if user.password_plain != password:
        user.password_plain = password
        user.password_hash = hash_password(password)
        changed = True
    if changed:
      db.commit()
  finally:
    db.close()


def _backfill_engineer_passwords() -> None:
  from app.database import SessionLocal
  from app.services.engineer_pool_service import sync_engineer_pool

  db = SessionLocal()
  try:
    sync_engineer_pool(db, purge_legacy=False)
    db.commit()
  finally:
    db.close()


def _backfill_stage1_point_codes() -> None:
  from app.database import SessionLocal
  from app.models import Point
  from app.point_codes import stage1_point_code

  db = SessionLocal()
  try:
    changed = False
    for point in db.query(Point).filter(Point.stage == 1).all():
      if not point.detonation_code:
        point.detonation_code = stage1_point_code(point)
        changed = True
    if changed:
      db.commit()
  finally:
    db.close()


def _backfill_loot_variant() -> None:
  from app.database import SessionLocal
  from app.models import Cache

  db = SessionLocal()
  try:
    changed = False
    for cache in db.query(Cache).filter(Cache.stage == 2, Cache.cache_kind == "film_loot").all():
      if not cache.loot_variant:
        cache.loot_variant = "film_passage"
        changed = True
    if changed:
      db.commit()
  finally:
    db.close()


def _backfill_qr_tokens() -> None:
  from app.database import SessionLocal
  from app.models import Cache, Point
  from app.qr_tokens import ensure_cache_qr_token, ensure_point_qr_token

  db = SessionLocal()
  try:
    changed = False
    for point in db.query(Point).all():
      if not point.qr_token:
        ensure_point_qr_token(point, db)
        changed = True
    for cache in db.query(Cache).all():
      if not cache.qr_token:
        ensure_cache_qr_token(cache, db)
        changed = True
    if changed:
      db.commit()
  finally:
    db.close()
