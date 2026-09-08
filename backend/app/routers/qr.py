from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cache, Point
from app.services.scenario_service import get_active_scenario_id

router = APIRouter(prefix="/api/public", tags=["public"])


class QrResolveResponse(BaseModel):
  kind: Literal["point", "cache"]
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
  raise HTTPException(status_code=404, detail="Ссылка недействительна")
