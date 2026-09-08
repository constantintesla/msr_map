from sqlalchemy.orm import Session

from app.tower.models import TowerConfig


def get_tower_config(db: Session, scenario_id: int) -> TowerConfig:
  cfg = db.query(TowerConfig).filter(TowerConfig.id == scenario_id).first()
  if cfg is None:
    cfg = TowerConfig(id=scenario_id)
    db.add(cfg)
    db.flush()
  return cfg
