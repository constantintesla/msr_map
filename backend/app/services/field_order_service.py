from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Cache, FieldOrder, Point, User
from app.services.game_service import get_or_create_game_state
from app.services.scenario_service import get_active_scenario_id
from app.services.stage2_assignment_service import is_cache_issued, is_stage2_active


def _resolve_target(db: Session, target_kind: str, target_id: int) -> tuple[str, float, float]:
  if target_kind == "point":
    row = db.query(Point).filter(Point.id == target_id).first()
  else:
    row = db.query(Cache).filter(Cache.id == target_id).first()
  if row is None:
    raise ValueError("Объект не найден")
  if target_kind == "cache":
    cache = row
    game = get_or_create_game_state(db)
    if (
      is_stage2_active(game)
      and cache.cache_kind == "film_loot"
      and not is_cache_issued(db, cache.id)
    ):
      raise ValueError("Цель ещё не выдана")
  return row.name, row.lat, row.lon


def dismiss_active_orders(db: Session, engineer_user_id: int) -> None:
  now = datetime.utcnow()
  rows = (
    db.query(FieldOrder)
    .filter(
      FieldOrder.scenario_id == get_active_scenario_id(db),
      FieldOrder.engineer_user_id == engineer_user_id,
      FieldOrder.dismissed_at.is_(None),
    )
    .all()
  )
  for row in rows:
    row.dismissed_at = now


def create_field_order(
  db: Session,
  *,
  commander: User,
  engineer_user_id: int,
  target_kind: str,
  target_id: int,
  note: str | None,
) -> FieldOrder:
  eng = db.query(User).filter(User.id == engineer_user_id, User.role == "engineer").first()
  if eng is None or eng.side != commander.side:
    raise ValueError("Инженер не найден")

  name, lat, lon = _resolve_target(db, target_kind, target_id)
  dismiss_active_orders(db, engineer_user_id)

  order = FieldOrder(
    scenario_id=get_active_scenario_id(db),
    side=commander.side or "A",
    commander_username=commander.username,
    engineer_user_id=eng.id,
    engineer_username=eng.username,
    target_kind=target_kind,
    target_id=target_id,
    target_name=name,
    target_lat=lat,
    target_lon=lon,
    note=(note or "").strip() or None,
  )
  db.add(order)
  db.flush()
  return order


def order_to_out(order: FieldOrder) -> dict:
  return {
    "id": order.id,
    "created_at": order.created_at,
    "side": order.side,
    "commander_username": order.commander_username,
    "engineer_username": order.engineer_username,
    "target_kind": order.target_kind,
    "target_id": order.target_id,
    "target_name": order.target_name,
    "target_lat": order.target_lat,
    "target_lon": order.target_lon,
    "note": order.note,
    "acknowledged_at": order.dismissed_at,
    "dismissed": order.dismissed_at is not None,
  }


def field_order_ws_packet(order: FieldOrder) -> dict:
  return {
    "e": "field_order_update",
    "t": order.side,
    "order_id": order.id,
    "u": order.engineer_username,
    "ack": order.dismissed_at is not None,
    "target": order.target_name,
  }
