from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Side(str, Enum):
  A = "A"
  B = "B"


class GameStatus(str, Enum):
  IDLE = "idle"
  RUNNING = "running"
  PAUSED = "paused"


class Scenario(Base):
  """Мероприятие: изолированный набор точек/схронов/настроек/состояния игры."""
  __tablename__ = "scenarios"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  name: Mapped[str] = mapped_column(String(128))
  slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
  kmz_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class User(Base):
  __tablename__ = "users"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
  password_hash: Mapped[str] = mapped_column(String(255))
  password_plain: Mapped[str | None] = mapped_column(String(16), nullable=True)
  role: Mapped[str] = mapped_column(String(16), default="player")
  side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  point_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("points.id"), nullable=True)
  cache_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("caches.id"), nullable=True)
  lpd_channel: Mapped[int | None] = mapped_column(Integer, nullable=True)  # LPD 1–69
  faction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("factions.id"), nullable=True)


class Point(Base):
  __tablename__ = "points"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  name: Mapped[str] = mapped_column(String(128))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  coefficient: Mapped[float] = mapped_column(Float, default=1.0)
  side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  stage: Mapped[int] = mapped_column(Integer, default=1)  # этап игры 1–3
  detonation_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
  destroyed: Mapped[bool] = mapped_column(Boolean, default=False)
  destroyed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  destroyed_by_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  admin_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
  enabled: Mapped[bool] = mapped_column(Boolean, default=True)
  qr_token: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True, index=True)

  hold_sessions: Mapped[list["HoldSession"]] = relationship(back_populates="point")


class Cache(Base):
  __tablename__ = "caches"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  name: Mapped[str] = mapped_column(String(128))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  detonation_code: Mapped[str] = mapped_column(String(6), default="0000")
  team_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  stage: Mapped[int] = mapped_column(Integer, default=3)
  cache_kind: Mapped[str] = mapped_column(String(16), default="post")  # film_loot | post
  destroyed: Mapped[bool] = mapped_column(Boolean, default=False)
  destroyed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  destroyed_by_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  delivery_reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  delivered_by_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  admin_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
  enabled: Mapped[bool] = mapped_column(Boolean, default=True)
  loot_variant: Mapped[str] = mapped_column(String(16), default="film_passage")  # film_passage | box_direct
  code_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  code_verified_by_side: Mapped[str | None] = mapped_column(String(1), nullable=True)
  code_verified_qr_token: Mapped[str | None] = mapped_column(String(24), nullable=True)
  qr_token: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True, index=True)

  hold_sessions: Mapped[list["CacheHoldSession"]] = relationship(back_populates="cache")


class CacheHoldSession(Base):
  """Удержание схрона этапа 3 перед детонацией."""
  __tablename__ = "cache_hold_sessions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  cache_id: Mapped[int] = mapped_column(Integer, ForeignKey("caches.id"))
  side: Mapped[str] = mapped_column(String(1))
  started_at: Mapped[datetime] = mapped_column(DateTime)
  ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  last_ping_at: Mapped[datetime] = mapped_column(DateTime)
  active: Mapped[bool] = mapped_column(Boolean, default=True)
  hold_ready: Mapped[bool] = mapped_column(Boolean, default=False)

  cache: Mapped["Cache"] = relationship(back_populates="hold_sessions")


class Landmark(Base):
  """Базы и точки старта из Задача1.kml (не участвуют в захвате/подрыве)."""
  __tablename__ = "landmarks"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  name: Mapped[str] = mapped_column(String(128))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  kind: Mapped[str] = mapped_column(String(16))  # base | start | base_start
  team_side: Mapped[str] = mapped_column(String(1))  # A=ЛК синие, B=СБГ красные
  enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class PointReconPhoto(Base):
  """Фото разведки КТ этапа 1 (фаза до захвата)."""
  __tablename__ = "point_recon_photos"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  point_id: Mapped[int] = mapped_column(Integer, ForeignKey("points.id"))
  side: Mapped[str] = mapped_column(String(1))
  user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
  username: Mapped[str] = mapped_column(String(64))
  media_filename: Mapped[str] = mapped_column(String(128))
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HoldSession(Base):
  __tablename__ = "hold_sessions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  point_id: Mapped[int] = mapped_column(Integer, ForeignKey("points.id"))
  side: Mapped[str] = mapped_column(String(1))
  started_at: Mapped[datetime] = mapped_column(DateTime)
  ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  last_ping_at: Mapped[datetime] = mapped_column(DateTime)
  active: Mapped[bool] = mapped_column(Boolean, default=True)
  hold_ready: Mapped[bool] = mapped_column(Boolean, default=False)
  user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

  point: Mapped["Point"] = relationship(back_populates="hold_sessions")


class GameState(Base):
  """1:1 со Scenario — id совпадает с id активного/дормантного сценария."""
  __tablename__ = "game_state"

  id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), primary_key=True)
  status: Mapped[str] = mapped_column(String(16), default=GameStatus.IDLE.value)
  started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  score_a: Mapped[int] = mapped_column(Integer, default=0)
  score_b: Mapped[int] = mapped_column(Integer, default=0)
  current_stage: Mapped[int] = mapped_column(Integer, default=1)  # активный этап 1–3
  engineers_per_side_a: Mapped[int] = mapped_column(Integer, default=5)
  engineers_per_side_b: Mapped[int] = mapped_column(Integer, default=5)
  stage2_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
  stage2_start_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  capture_radius_m: Mapped[int] = mapped_column(Integer, default=10)
  disable_capture_distance: Mapped[bool] = mapped_column(Boolean, default=False)
  stage1_recapturable: Mapped[bool] = mapped_column(Boolean, default=True)
  point_capture_seconds: Mapped[int] = mapped_column(Integer, default=120)
  point_hold_ping_seconds: Mapped[int] = mapped_column(Integer, default=120)
  post_hold_seconds: Mapped[int] = mapped_column(Integer, default=600)
  post_hold_ping_seconds: Mapped[int] = mapped_column(Integer, default=120)
  stage2_issue_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
  stage2_issue_mode: Mapped[str] = mapped_column(String(16), default="random")  # random | sequential
  stage2_last_issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  stage2_sequential_index: Mapped[int] = mapped_column(Integer, default=0)
  stage1_recon_minutes: Mapped[int] = mapped_column(Integer, default=120)
  stage1_slot_minutes: Mapped[int] = mapped_column(Integer, default=120)
  stage1_hold_slots_json: Mapped[str | None] = mapped_column(Text, nullable=True)
  stage1_current_slot: Mapped[int] = mapped_column(Integer, default=-1)  # legacy / ended marker
  stage1_slots_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  gps_accuracy_bonus_max_m: Mapped[int] = mapped_column(Integer, default=20)
  gps_min_accuracy_for_capture_m: Mapped[int] = mapped_column(Integer, default=0)
  gps_lat_offset: Mapped[float] = mapped_column(Float, default=0.0)
  gps_lon_offset: Mapped[float] = mapped_column(Float, default=0.0)
  game_session_id: Mapped[int] = mapped_column(Integer, default=1)


class MovementTrackPoint(Base):
  """История GPS-позиций инженера в рамках игровой сессии."""
  __tablename__ = "movement_track_points"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  game_session_id: Mapped[int] = mapped_column(Integer, index=True)
  user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
  username: Mapped[str] = mapped_column(String(64))
  side: Mapped[str] = mapped_column(String(1))
  label: Mapped[str] = mapped_column(String(128))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  accuracy: Mapped[float] = mapped_column(Float, default=0.0)
  recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Stage2Assignment(Base):
  """Выданная цель этапа 2 (одинаковая для обеих сторон)."""
  __tablename__ = "stage2_assignments"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  cache_id: Mapped[int] = mapped_column(Integer, ForeignKey("caches.id"))
  assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  round_number: Mapped[int] = mapped_column(Integer, default=1)


class EventLog(Base):
  __tablename__ = "event_log"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("scenarios.id"), nullable=True, index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  event_type: Mapped[str] = mapped_column(String(64))
  payload: Mapped[str] = mapped_column(Text, default="{}")


class ChatMessage(Base):
  """Чат штаб ↔ командование / инженеры (сторона A или B)."""
  __tablename__ = "chat_messages"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  side: Mapped[str] = mapped_column(String(1))  # A | B
  thread: Mapped[str] = mapped_column(String(8), default="cmd")  # cmd | eng
  sender_role: Mapped[str] = mapped_column(String(16))  # admin | commander | engineer
  sender_username: Mapped[str] = mapped_column(String(64))
  text: Mapped[str | None] = mapped_column(Text, nullable=True)
  media_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # image | video
  media_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
  media_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
  recipient_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
  faction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("factions.id"), nullable=True)


class EngineerLocation(Base):
  """Последняя GPS-позиция инженера (обновляется с телефона)."""
  __tablename__ = "engineer_locations"

  user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  username: Mapped[str] = mapped_column(String(64))
  side: Mapped[str] = mapped_column(String(1))
  label: Mapped[str] = mapped_column(String(128))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  accuracy: Mapped[float] = mapped_column(Float, default=0.0)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  faction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("factions.id"), nullable=True)


class FieldOrder(Base):
  """Необязательный приказ командования инженеру (точка или схрон)."""
  __tablename__ = "field_orders"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True, default=1)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
  side: Mapped[str] = mapped_column(String(1))
  commander_username: Mapped[str] = mapped_column(String(64))
  engineer_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
  engineer_username: Mapped[str] = mapped_column(String(64))
  target_kind: Mapped[str] = mapped_column(String(8))  # point | cache
  target_id: Mapped[int] = mapped_column(Integer)
  target_name: Mapped[str] = mapped_column(String(128))
  target_lat: Mapped[float] = mapped_column(Float)
  target_lon: Mapped[float] = mapped_column(Float)
  note: Mapped[str | None] = mapped_column(Text, nullable=True)
  dismissed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  faction_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("factions.id"), nullable=True)
