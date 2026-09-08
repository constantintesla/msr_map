from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
  return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
  return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
  to_encode = data.copy()
  expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
  to_encode.update({"exp": expire})
  return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
  db: Annotated[Session, Depends(get_db)],
) -> User:
  if credentials is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
  try:
    payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
    username: str | None = payload.get("sub")
    if username is None:
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
  except JWTError as exc:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен") from exc

  user = db.query(User).filter(User.username == username).first()
  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
  return user


def get_optional_user(
  credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
  db: Annotated[Session, Depends(get_db)],
) -> User | None:
  if credentials is None:
    return None
  try:
    payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
    username: str | None = payload.get("sub")
    if username is None:
      return None
  except JWTError:
    return None
  return db.query(User).filter(User.username == username).first()


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
  if user.role != "admin":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для администратора")
  return user


def require_commander(user: Annotated[User, Depends(get_current_user)]) -> User:
  if user.role != "commander":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для командования")
  if not user.side:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="У учётки нет стороны")
  return user


def require_engineer(user: Annotated[User, Depends(get_current_user)]) -> User:
  if user.role != "engineer":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для инженеров")
  return user


def require_tower_user(user: Annotated[User, Depends(get_current_user)]) -> User:
  if user.role not in ("faction", "commander") or not user.faction_id:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для сторон Башни")
  return user


def require_tower_commander(user: Annotated[User, Depends(require_tower_user)]) -> User:
  if user.role != "commander":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для командования стороны")
  return user
