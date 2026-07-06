from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_engineer
from app.database import get_db
from app.lpd_channels import lpd_frequency_mhz, lpd_label
from app.models import FieldOrder, User
from app.routers import ws
from app.schemas import EngineerProfileOut, FieldOrderDismissResponse, FieldOrderOut
from app.services.field_order_service import field_order_ws_packet, order_to_out

router = APIRouter(prefix="/api/engineer", tags=["engineer"])


def _profile_out(user: User) -> EngineerProfileOut:
  return EngineerProfileOut(
    username=user.username,
    side=user.side or "A",
    lpd_channel=user.lpd_channel,
    lpd_frequency_mhz=lpd_frequency_mhz(user.lpd_channel),
    lpd_label=lpd_label(user.lpd_channel),
    point_id=user.point_id,
    cache_id=user.cache_id,
  )


@router.get("/profile", response_model=EngineerProfileOut)
def engineer_profile(
  user: Annotated[User, Depends(require_engineer)],
):
  return _profile_out(user)


@router.get("/orders/active", response_model=list[FieldOrderOut])
def engineer_active_orders(
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  rows = (
    db.query(FieldOrder)
    .filter(FieldOrder.engineer_user_id == user.id, FieldOrder.dismissed_at.is_(None))
    .order_by(FieldOrder.created_at.desc())
    .limit(5)
    .all()
  )
  return [FieldOrderOut(**order_to_out(r)) for r in rows]


@router.post("/orders/{order_id}/dismiss", response_model=FieldOrderDismissResponse)
async def engineer_dismiss_order(
  order_id: int,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  order = (
    db.query(FieldOrder)
    .filter(FieldOrder.id == order_id, FieldOrder.engineer_user_id == user.id)
    .first()
  )
  if order is None:
    raise HTTPException(status_code=404, detail="Приказ не найден")
  if order.dismissed_at is None:
    from datetime import datetime

    order.dismissed_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    await ws.broadcast_field_order_update(field_order_ws_packet(order), order.side)

  return FieldOrderDismissResponse(ok=True, order=FieldOrderOut(**order_to_out(order)))
