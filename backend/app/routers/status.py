from typing import Annotated



from fastapi import APIRouter, Depends

from sqlalchemy.orm import Session



from app.auth import get_optional_user

from app.database import get_db

from app.models import User

from app.routers import ws

from app.schemas import StatusResponse

from app.services.hold_service import refresh_active_hold_progress

from app.services.status_service import build_status_response



router = APIRouter(prefix="/api", tags=["status"])





@router.get("/status", response_model=StatusResponse)

async def get_status(

  db: Annotated[Session, Depends(get_db)],

  user: Annotated[User | None, Depends(get_optional_user)] = None,

):

  """Статус для инженеров (карта на точке/схроне)."""

  for packet in refresh_active_hold_progress(db):

    await ws.broadcast_hold_update(packet)

  return build_status_response(

    db,

    stage2_player_view=True,

    viewer_side=user.side if user else None,

    viewer_role=user.role if user else None,

  )


