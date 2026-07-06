from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Cache, Point

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
  point = db.query(Point).filter(Point.qr_token == token).first()
  if point:
    return QrResolveResponse(kind="point", id=point.id)
  cache = db.query(Cache).filter(Cache.qr_token == token).first()
  if cache:
    return QrResolveResponse(kind="cache", id=cache.id)
  raise HTTPException(status_code=404, detail="Ссылка недействительна")
