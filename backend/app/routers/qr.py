from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cache, Point
from app.services.scenario_service import get_active_scenario_id
from app.tower.models import Faction, UrPoint

router = APIRouter(prefix="/api/public", tags=["public"])


class QrResolveResponse(BaseModel):
  kind: Literal["point", "cache", "tower_village", "tower_ur_point"]
  id: int


@router.get("/qr/{token}", response_model=QrResolveResponse)
def resolve_qr_token(
  token: str,
  db: Annotated[Session, Depends(get_db)],
):
  """Разрешить непрозрачный QR-токен в тип объекта и id (для входа по табличке)."""
  scenario_id = get_active_scenario_id(db)
  point = db.query(Point).filter(Point.qr_token == token, Point.scenario_id == scenario_id).first()
  if point:
    return QrResolveResponse(kind="point", id=point.id)
  cache = db.query(Cache).filter(Cache.qr_token == token, Cache.scenario_id == scenario_id).first()
  if cache:
    return QrResolveResponse(kind="cache", id=cache.id)
  # Faction/UrPoint QR — глобально уникальны, без привязки к активному сценарию
  # (Башня должна открываться и до, и после переключения общего активного сценария).
  faction = db.query(Faction).filter(Faction.qr_token == token).first()
  if faction:
    return QrResolveResponse(kind="tower_village", id=faction.id)
  ur_point = db.query(UrPoint).filter(UrPoint.qr_token == token).first()
  if ur_point:
    return QrResolveResponse(kind="tower_ur_point", id=ur_point.id)
  raise HTTPException(status_code=404, detail="Ссылка недействительна")
