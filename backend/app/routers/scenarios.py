from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import User
from app.routers import ws
from app.schemas import ScenarioCreate, ScenarioOut
from app.services.scenario_service import activate_scenario, archive_scenario, create_scenario, list_scenarios

router = APIRouter(prefix="/api/admin/scenarios", tags=["scenarios"])


def _out(scenario) -> ScenarioOut:
  return ScenarioOut(
    id=scenario.id,
    name=scenario.name,
    slug=scenario.slug,
    is_active=scenario.is_active,
    created_at=scenario.created_at,
  )


@router.get("", response_model=list[ScenarioOut])
def admin_list_scenarios(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  return [_out(s) for s in list_scenarios(db)]


@router.post("", response_model=ScenarioOut)
def admin_create_scenario(
  body: ScenarioCreate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  scenario = create_scenario(db, body.name.strip())
  return _out(scenario)


@router.post("/{scenario_id}/activate", response_model=ScenarioOut)
async def admin_activate_scenario(
  scenario_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    scenario = activate_scenario(db, scenario_id)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  await ws.broadcast_scenario_switched(scenario.id)
  return _out(scenario)


@router.post("/{scenario_id}/archive", response_model=ScenarioOut)
def admin_archive_scenario(
  scenario_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    scenario = archive_scenario(db, scenario_id)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  return _out(scenario)
