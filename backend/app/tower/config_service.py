import json

from sqlalchemy.orm import Session

from app.tower.models import TowerConfig

DEFAULT_PHASES = [
  "Этап 1 — Противостояние деревень (12:00–19:00, 12.09)",
  "Пересменка / гражданская война (19:30–22:30, 12.09)",
  "Этап 2 — Шахты (23:00–03:00, 13.09)",
  "Перерыв — свободная охота (03:00–08:00, 13.09)",
  "Этап 3 — Сход старейшин (09:00–11:00, 13.09)",
  "Этап 4 — Эвакуация (11:00–15:00, 13.09)",
]


def get_tower_config(db: Session, scenario_id: int) -> TowerConfig:
  cfg = db.query(TowerConfig).filter(TowerConfig.id == scenario_id).first()
  if cfg is None:
    cfg = TowerConfig(id=scenario_id)
    db.add(cfg)
    db.flush()
  return cfg


def get_phases(cfg: TowerConfig) -> list[str]:
  if not cfg.phases_json:
    return list(DEFAULT_PHASES)
  try:
    phases = json.loads(cfg.phases_json)
  except (json.JSONDecodeError, TypeError):
    return list(DEFAULT_PHASES)
  return phases if isinstance(phases, list) and phases else list(DEFAULT_PHASES)


def set_phases(cfg: TowerConfig, phases: list[str]) -> None:
  cleaned = [p.strip() for p in phases if p and p.strip()]
  cfg.phases_json = json.dumps(cleaned, ensure_ascii=False)
  if cfg.current_phase >= len(cleaned):
    cfg.current_phase = max(0, len(cleaned) - 1)


def current_phase_name(cfg: TowerConfig) -> str | None:
  phases = get_phases(cfg)
  if 0 <= cfg.current_phase < len(phases):
    return phases[cfg.current_phase]
  return None
