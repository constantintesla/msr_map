"""Модели сценария «Башня»: стороны (факции), деревенские схроны, укрепрайоны.

Отдельный модуль поверх той же Base — параллельно движку A/B в app.models,
ничего оттуда не меняет и не трогает. Сторон может быть произвольное
количество (не только 2), поэтому Faction — таблица, а не String(1)/enum.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Faction(Base):
  """Сторона в рамках сценария: СБГ / ДРГ / деревня и т.п."""
  __tablename__ = "factions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True)
  code: Mapped[str] = mapped_column(String(32), index=True)  # slug: sbg / drg / prvonek / korbul
  name: Mapped[str] = mapped_column(String(64))
  kind: Mapped[str] = mapped_column(String(16), default="ops")  # village | ops
  color: Mapped[str | None] = mapped_column(String(7), nullable=True)
  lat: Mapped[float | None] = mapped_column(Float, nullable=True)
  lon: Mapped[float | None] = mapped_column(Float, nullable=True)
  qr_token: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True, index=True)
  join_token: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True, index=True)
  manual_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
  elder_photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
  elder_note: Mapped[str | None] = mapped_column(Text, nullable=True)
  drop_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
  drop_lon: Mapped[float | None] = mapped_column(Float, nullable=True)


class VillageCacheTarget(Base):
  """Один из схронов деревни — координата, раскрываемая враждебной стороне по расписанию."""
  __tablename__ = "tower_village_cache_targets"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True)
  faction_id: Mapped[int] = mapped_column(Integer, ForeignKey("factions.id"), index=True)
  name: Mapped[str] = mapped_column(String(64))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  reveal_order: Mapped[int] = mapped_column(Integer)


class VillageRevealState(Base):
  """Сколько схронов target_faction уже раскрыто viewer_faction, и когда в последний раз."""
  __tablename__ = "tower_village_reveal_state"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True)
  target_faction_id: Mapped[int] = mapped_column(Integer, ForeignKey("factions.id"), index=True)
  viewer_faction_id: Mapped[int] = mapped_column(Integer, ForeignKey("factions.id"), index=True)
  revealed_count: Mapped[int] = mapped_column(Integer, default=0)
  last_revealed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TowerConfig(Base):
  """1:1 со Scenario — расписание раскрытия схронов и тайминги удержания УР."""
  __tablename__ = "tower_config"

  id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), primary_key=True)
  reveal_schedule_json: Mapped[str | None] = mapped_column(Text, nullable=True)
  ur_sync_window_seconds: Mapped[int] = mapped_column(Integer, default=180)
  ur_hold_seconds: Mapped[int] = mapped_column(Integer, default=1200)


class UrZone(Base):
  """Укрепрайон — группа из 3 точек КПП, которые СБГ удерживает синхронно."""
  __tablename__ = "tower_ur_zones"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True)
  name: Mapped[str] = mapped_column(String(32))
  order: Mapped[int] = mapped_column(Integer, default=0)
  status: Mapped[str] = mapped_column(String(16), default="idle")  # idle|syncing|holding|captured
  sync_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  hold_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

  points: Mapped[list["UrPoint"]] = relationship(back_populates="zone")


class UrPoint(Base):
  """Точка КПП внутри укрепрайона."""
  __tablename__ = "tower_ur_points"

  id: Mapped[int] = mapped_column(Integer, primary_key=True)
  scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"), index=True)
  zone_id: Mapped[int] = mapped_column(Integer, ForeignKey("tower_ur_zones.id"), index=True)
  name: Mapped[str] = mapped_column(String(32))
  lat: Mapped[float] = mapped_column(Float)
  lon: Mapped[float] = mapped_column(Float)
  qr_token: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True, index=True)
  manual_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
  last_sbg_scan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

  zone: Mapped["UrZone"] = relationship(back_populates="points")
