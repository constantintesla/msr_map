from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.map_grid import GRID_IMAGE_NAME, ensure_map_grid_assets
from app.schemas import MapGridOut

router = APIRouter(prefix="/api/map", tags=["map"])


@router.get("/grid", response_model=MapGridOut | None)
def get_map_grid():
  """Метаданные буквенно-цифровой сетки из map.kmz."""
  overlay, image_path = ensure_map_grid_assets()
  if overlay is None or image_path is None:
    return None
  return MapGridOut(
    north=overlay.north,
    south=overlay.south,
    east=overlay.east,
    west=overlay.west,
    image_url="/api/map/grid/image",
  )


@router.get("/grid/image")
def get_map_grid_image():
  """PNG-оверлей сетки (прозрачный фон, линии и подписи ячеек)."""
  _, image_path = ensure_map_grid_assets()
  if image_path is None or not image_path.is_file():
    raise HTTPException(status_code=404, detail="Сетка не найдена")
  return FileResponse(
    path=Path(image_path),
    media_type="image/png",
    filename=GRID_IMAGE_NAME,
  )
