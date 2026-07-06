from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.database import get_db
from app.lpd_channels import lpd_frequency_mhz, lpd_label
from app.models import User
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]):
  user = db.query(User).filter(User.username == body.username).first()
  if user is None or not verify_password(body.password, user.password_hash):
    raise HTTPException(status_code=401, detail="Неверный логин или пароль")

  token = create_access_token({"sub": user.username, "role": user.role})
  return TokenResponse(
    access_token=token,
    user_id=user.id,
    role=user.role,
    side=user.side,
    point_id=user.point_id,
    cache_id=user.cache_id,
    lpd_channel=user.lpd_channel,
    lpd_frequency_mhz=lpd_frequency_mhz(user.lpd_channel),
    lpd_label=lpd_label(user.lpd_channel),
  )
