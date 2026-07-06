import asyncio
from io import BytesIO

import pytest
from fastapi import HTTPException
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.chat_media import save_chat_media

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64


def _file(name: str, data: bytes, content_type: str) -> UploadFile:
  return UploadFile(
    file=BytesIO(data),
    filename=name,
    headers=Headers({"content-type": content_type}),
  )


@pytest.mark.parametrize(
  "name,content_type",
  [
    ("photo.jpg", "image/jpeg"),
    ("photo.jpg", ""),
    ("photo.jpg", "application/octet-stream"),
    ("photo.jpg", "image/jpg"),
  ],
)
def test_accepts_jpeg_with_various_declared_types(name: str, content_type: str) -> None:
  media_type, _, original = asyncio.run(save_chat_media(_file(name, JPEG, content_type)))
  assert media_type == "image"
  assert original == name


def test_rejects_heic_with_helpful_message() -> None:
  with pytest.raises(HTTPException) as exc:
    asyncio.run(save_chat_media(_file("IMG_0001.HEIC", HEIC, "image/heic")))
  assert exc.value.status_code == 400
  assert "HEIC" in exc.value.detail
