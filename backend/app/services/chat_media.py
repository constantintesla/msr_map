import mimetypes
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads" / "chat"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_VIDEO_BYTES = 80 * 1024 * 1024

ALLOWED_IMAGE = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
ALLOWED_VIDEO = frozenset({"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"})
ALLOWED_MEDIA = ALLOWED_IMAGE | ALLOWED_VIDEO
UNSUPPORTED_IMAGE = frozenset({"image/heic", "image/heif"})

MIME_ALIASES = {
  "image/jpg": "image/jpeg",
  "image/pjpeg": "image/jpeg",
  "image/x-png": "image/png",
}

EXT_BY_TYPE = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/gif": ".gif",
  "video/mp4": ".mp4",
  "video/webm": ".webm",
  "video/quicktime": ".mov",
  "video/x-msvideo": ".avi",
}

EXT_TO_TYPE = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".jpe": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
  ".gif": "image/gif",
  ".heic": "image/heic",
  ".heif": "image/heif",
  ".mp4": "video/mp4",
  ".m4v": "video/mp4",
  ".webm": "video/webm",
  ".mov": "video/quicktime",
  ".avi": "video/x-msvideo",
}


def ensure_upload_dir() -> Path:
  UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
  return UPLOAD_ROOT


def _normalize_mime(content_type: str) -> str:
  ct = (content_type or "").split(";")[0].strip().lower()
  return MIME_ALIASES.get(ct, ct)


def _sniff_mime(data: bytes, filename: str) -> str | None:
  if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
    return "image/jpeg"
  if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
    return "image/png"
  if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
    return "image/webp"
  if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
    return "image/gif"
  if len(data) >= 12 and data[4:8] == b"ftyp":
    brand = data[8:12]
    if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
      return "image/heic"
    if brand in (b"qt  ", b"moov"):
      return "video/quicktime"
    if brand.startswith(b"mp") or brand in (b"isom", b"M4V ", b"mmp4", b"iso2"):
      return "video/mp4"
  if len(data) >= 4 and data[:4] == b"\x1aE\xdf\xa3":
    return "video/webm"
  return EXT_TO_TYPE.get(Path(filename or "").suffix.lower())


def _resolve_mime(declared: str, data: bytes, filename: str) -> str:
  content_type = _normalize_mime(declared)
  if content_type in ALLOWED_MEDIA:
    return content_type
  sniffed = _sniff_mime(data, filename)
  if sniffed in ALLOWED_MEDIA:
    return sniffed
  if content_type in UNSUPPORTED_IMAGE or sniffed in UNSUPPORTED_IMAGE:
    return sniffed or content_type
  if content_type in ("", "application/octet-stream", "binary/octet-stream") and sniffed:
    return sniffed
  return content_type or sniffed or ""


def _heic_error() -> HTTPException:
  return HTTPException(
    status_code=400,
    detail=(
      "Формат HEIC/HEIF не поддерживается. "
      "На iPhone: Настройки → Камера → Форматы → «Совместимость», "
      "или прикрепите JPEG/PNG из галереи."
    ),
  )


async def save_chat_media(file: UploadFile) -> tuple[str, str, str]:
  """Сохраняет файл, возвращает (media_type, relative_path, original_name)."""
  data = await file.read()
  if not data:
    raise HTTPException(status_code=400, detail="Пустой файл")

  content_type = _resolve_mime(file.content_type or "", data, file.filename or "")
  if content_type in UNSUPPORTED_IMAGE:
    raise _heic_error()
  if content_type not in ALLOWED_MEDIA:
    raise HTTPException(status_code=400, detail="Допустимы фото (JPEG/PNG/WebP/GIF) и видео (MP4/WebM/MOV)")

  max_size = MAX_VIDEO_BYTES if content_type in ALLOWED_VIDEO else MAX_IMAGE_BYTES
  if len(data) > max_size:
    mb = max_size // (1024 * 1024)
    raise HTTPException(status_code=400, detail=f"Файл слишком большой (макс. {mb} МБ)")

  ext = EXT_BY_TYPE.get(content_type) or mimetypes.guess_extension(content_type) or ""
  if not ext:
    raise HTTPException(status_code=400, detail="Неизвестный тип файла")

  media_type = "video" if content_type in ALLOWED_VIDEO else "image"
  root = ensure_upload_dir()
  filename = f"{uuid.uuid4().hex}{ext}"
  path = root / filename
  path.write_bytes(data)

  original = file.filename or filename
  return media_type, filename, original


def resolve_media_path(stored_name: str) -> Path:
  root = ensure_upload_dir().resolve()
  path = (root / stored_name).resolve()
  if not str(path).startswith(str(root)):
    raise HTTPException(status_code=404, detail="Файл не найден")
  if not path.is_file():
    raise HTTPException(status_code=404, detail="Файл не найден")
  return path
