"""Сценарии (мероприятия): создание, активация, разрешение текущего активного."""

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Scenario, User

DEFAULT_SCENARIO_NAME = "Мероприятие 1"
DEFAULT_SCENARIO_SLUG = "default"


def _slugify(name: str, db: Session) -> str:
  base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "scenario"
  slug = base
  n = 1
  while db.query(Scenario).filter(Scenario.slug == slug).first() is not None:
    n += 1
    slug = f"{base}-{n}"
  return slug


def _create_scenario_row(db: Session, name: str, *, is_active: bool, slug: str | None = None) -> Scenario:
  scenario = Scenario(
    name=name,
    slug=slug or _slugify(name, db),
    is_active=is_active,
    created_at=datetime.utcnow(),
  )
  db.add(scenario)
  db.flush()
  return scenario


def get_active_scenario_id(db: Session) -> int:
  scenario = db.query(Scenario).filter(Scenario.is_active.is_(True)).first()
  if scenario is not None:
    return scenario.id
  # Бутстрап на пустой БД или если активный флаг случайно потерян.
  scenario = db.query(Scenario).order_by(Scenario.id).first()
  if scenario is None:
    scenario = _create_scenario_row(db, DEFAULT_SCENARIO_NAME, is_active=True, slug=DEFAULT_SCENARIO_SLUG)
    db.commit()
    return scenario.id
  scenario.is_active = True
  db.commit()
  return scenario.id


def list_scenarios(db: Session) -> list[Scenario]:
  return db.query(Scenario).filter(Scenario.archived_at.is_(None)).order_by(Scenario.created_at).all()


def create_scenario(db: Session, name: str) -> Scenario:
  scenario = _create_scenario_row(db, name, is_active=False)
  db.commit()
  db.refresh(scenario)
  return scenario


def activate_scenario(db: Session, scenario_id: int) -> Scenario:
  from app.services.engineer_pool_service import sync_engineer_pool

  scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
  if scenario is None:
    raise ValueError("Сценарий не найден")
  if scenario.archived_at is not None:
    raise ValueError("Сценарий архивирован")

  db.query(Scenario).filter(Scenario.is_active.is_(True)).update(
    {Scenario.is_active: False}, synchronize_session=False
  )
  scenario.is_active = True

  db.query(User).filter(User.point_id.isnot(None)).update(
    {User.point_id: None}, synchronize_session=False
  )
  db.query(User).filter(User.cache_id.isnot(None)).update(
    {User.cache_id: None}, synchronize_session=False
  )
  db.flush()

  sync_engineer_pool(db)
  db.commit()
  db.refresh(scenario)
  return scenario


def archive_scenario(db: Session, scenario_id: int) -> Scenario:
  scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
  if scenario is None:
    raise ValueError("Сценарий не найден")
  if scenario.is_active:
    raise ValueError("Нельзя архивировать активный сценарий")
  scenario.archived_at = datetime.utcnow()
  db.commit()
  db.refresh(scenario)
  return scenario
