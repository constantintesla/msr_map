import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "point_recon"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
EXT_BY_TYPE = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/gif": ".gif",
}


def ensure_upload_dir() -> Path:
  UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
  return UPLOAD_ROOT


async def save_point_recon_photo(file: UploadFile) -> str:
  """Сохраняет фото разведки, возвращает имя файла."""
  content_type = (file.content_type or "").split(";")[0].strip().lower()
  if content_type not in ALLOWED_IMAGE:
    raise HTTPException(status_code=400, detail="Допустимы фото JPEG, PNG, WebP или GIF")

  data = await file.read()
  if not data:
    raise HTTPException(status_code=400, detail="Пустой файл")
  if len(data) > MAX_IMAGE_BYTES:
    raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 12 МБ)")

  ext = EXT_BY_TYPE.get(content_type) or mimetypes.guess_extension(content_type) or ".jpg"
  root = ensure_upload_dir()
  filename = f"{uuid.uuid4().hex}{ext}"
  (root / filename).write_bytes(data)
  return filename


def resolve_point_recon_path(stored_name: str) -> Path:
  root = ensure_upload_dir().resolve()
  path = (root / stored_name).resolve()
  if not str(path).startswith(str(root)) or not path.is_file():
    raise HTTPException(status_code=404, detail="Файл не найден")
  return path
