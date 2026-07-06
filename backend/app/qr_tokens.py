"""Непрозрачные ссылки для QR на табличках (без /cache/id и /point/id)."""

import secrets

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Cache, Point

TOKEN_LEN = 16


def generate_qr_token() -> str:
  return secrets.token_urlsafe(TOKEN_LEN)[:TOKEN_LEN]


def qr_entry_path(token: str) -> str:
  return f"/g/{token}"


def qr_entry_url(token: str) -> str:
  base = settings.public_app_url.rstrip("/")
  return f"{base}/#{qr_entry_path(token)}"


def ensure_point_qr_token(point: Point, db: Session | None = None) -> str:
  if point.qr_token:
    return point.qr_token
  for _ in range(20):
    token = generate_qr_token()
    clash_p = db.query(Point).filter(Point.qr_token == token).first() if db else None
    clash_c = db.query(Cache).filter(Cache.qr_token == token).first() if db else None
    if not clash_p and not clash_c:
      point.qr_token = token
      return token
  raise RuntimeError("Не удалось сгенерировать уникальный QR-токен")


def ensure_cache_qr_token(cache: Cache, db: Session | None = None) -> str:
  if cache.qr_token:
    return cache.qr_token
  for _ in range(20):
    token = generate_qr_token()
    clash_p = db.query(Point).filter(Point.qr_token == token).first() if db else None
    clash_c = db.query(Cache).filter(Cache.qr_token == token).first() if db else None
    if not clash_p and not clash_c:
      cache.qr_token = token
      return token
  raise RuntimeError("Не удалось сгенерировать уникальный QR-токен")
