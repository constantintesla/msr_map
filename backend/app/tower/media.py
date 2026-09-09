"""Фото старейшины для деревенского QR-досье — публичная раздача (без auth),
т.к. <img src> не может слать Bearer-заголовок."""

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import settings

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "tower_elder"
MAX_BYTES = 8 * 1024 * 1024
EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
EXT_BY_SUFFIX = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".webp": ".webp"}


def _ensure_dir() -> Path:
  UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
  return UPLOAD_ROOT


async def save_elder_photo(file: UploadFile) -> str:
  data = await file.read()
  if not data:
    raise HTTPException(status_code=400, detail="Пустой файл")
  if len(data) > MAX_BYTES:
    raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 8 МБ)")

  content_type = (file.content_type or "").split(";")[0].strip().lower()
  ext = EXT_BY_TYPE.get(content_type) or EXT_BY_SUFFIX.get(Path(file.filename or "").suffix.lower())
  if not ext:
    raise HTTPException(status_code=400, detail="Допустимы фото JPEG / PNG / WebP")

  root = _ensure_dir()
  filename = f"{uuid.uuid4().hex}{ext}"
  (root / filename).write_bytes(data)
  return filename


def resolve_elder_photo_path(filename: str) -> Path:
  root = _ensure_dir().resolve()
  path = (root / filename).resolve()
  if not str(path).startswith(str(root)) or not path.is_file():
    raise HTTPException(status_code=404, detail="Фото не найдено")
  return path


def elder_photo_url(filename: str | None) -> str | None:
  if not filename:
    return None
  base = settings.public_app_url.rstrip("/")
  return f"{base}/api/public/tower/elder-photo/{filename}"
