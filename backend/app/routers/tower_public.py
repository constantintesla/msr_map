"""Публичная (без авторизации) саморегистрация игрока по ссылке своей стороны:
GET резолвит join_token в название стороны для заголовка страницы, POST
заводит аккаунт (позывной + 4-значный PIN) и сразу логинит."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.database import get_db
from app.lpd_channels import lpd_frequency_mhz, lpd_label
from app.models import User
from app.schemas import TokenResponse
from app.tower.media import resolve_elder_photo_path
from app.tower.models import Faction
from app.tower.schemas import TowerJoinInfoOut, TowerRegisterRequest

router = APIRouter(prefix="/api/public/tower", tags=["tower-public"])


def _find_faction_by_join_token(db: Session, token: str) -> Faction:
  """join_token уникален глобально (unique=True) — резолвим без привязки к
  «активному» сценарию движка, чтобы ссылки регистрации работали и до, и
  после активации Башни в общем переключателе сценариев."""
  faction = db.query(Faction).filter(Faction.join_token == token).first()
  if faction is None:
    raise HTTPException(status_code=404, detail="Ссылка недействительна")
  return faction


@router.get("/join/{token}", response_model=TowerJoinInfoOut)
def join_info(token: str, db: Annotated[Session, Depends(get_db)]):
  faction = _find_faction_by_join_token(db, token)
  return TowerJoinInfoOut(faction_code=faction.code, faction_name=faction.name)


@router.post("/join/{token}", response_model=TokenResponse)
def register(token: str, body: TowerRegisterRequest, db: Annotated[Session, Depends(get_db)]):
  faction = _find_faction_by_join_token(db, token)
  callsign = body.callsign.strip()
  if not callsign:
    raise HTTPException(status_code=400, detail="Введите позывной")
  if db.query(User).filter(User.username == callsign).first() is not None:
    raise HTTPException(status_code=409, detail="Такой позывной уже занят, придумайте другой")

  user = User(
    username=callsign,
    password_hash=hash_password(body.pin),
    password_plain=body.pin,
    role="faction",
    faction_id=faction.id,
  )
  db.add(user)
  try:
    db.commit()
  except IntegrityError as exc:
    db.rollback()
    raise HTTPException(status_code=409, detail="Такой позывной уже занят, придумайте другой") from exc
  db.refresh(user)

  token_value = create_access_token({"sub": user.username, "role": user.role})
  return TokenResponse(
    access_token=token_value,
    user_id=user.id,
    role=user.role,
    side=user.side,
    lpd_channel=user.lpd_channel,
    lpd_frequency_mhz=lpd_frequency_mhz(user.lpd_channel),
    lpd_label=lpd_label(user.lpd_channel),
    faction_id=user.faction_id,
    faction_code=faction.code,
    faction_name=faction.name,
  )


@router.get("/elder-photo/{filename}")
def get_elder_photo(filename: str):
  path = resolve_elder_photo_path(filename)
  return FileResponse(path)
