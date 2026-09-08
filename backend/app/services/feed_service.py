import json

from sqlalchemy.orm import Session

from app.models import Cache, EventLog, Point
from app.services.scenario_service import get_active_scenario_id

SIDE_LABEL = {"A": "ЛК", "B": "СБГ"}

# Шумные события не показываем командованию
_SKIP_EVENTS = frozenset(
  {
    "hold_ping",
    "cache_hold_ping",
    "admin_stage2_code",
    "admin_mertvyak",
  }
)


def _point_name(db: Session, point_id: int | None) -> str:
  if not point_id:
    return "точка"
  p = db.query(Point).filter(Point.id == point_id).first()
  return p.name if p else f"КТ #{point_id}"


def _cache_name(db: Session, cache_id: int | None) -> str:
  if not cache_id:
    return "схрон"
  c = db.query(Cache).filter(Cache.id == cache_id).first()
  return c.name if c else f"схрон #{cache_id}"


def _side_label(side: str | None) -> str:
  if not side:
    return "—"
  return SIDE_LABEL.get(side, side)


def format_event_text(db: Session, event_type: str, payload: dict) -> str | None:
  if event_type in _SKIP_EVENTS:
    return None

  if event_type == "admin_broadcast":
    return payload.get("message") or "Сообщение штаба"

  if event_type == "game_start":
    return "Игра началась"
  if event_type == "game_pause":
    return "Игра на паузе"
  if event_type == "game_reset":
    return "Игра сброшена"
  if event_type == "stage_change":
    return f"Переключён этап {payload.get('stage', '?')}"

  if event_type == "hold_start":
    return f"{_point_name(db, payload.get('point_id'))}: начато удержание (сторона {_side_label(payload.get('side'))})"
  if event_type == "hold_leave":
    return f"{_point_name(db, payload.get('point_id'))}: удержание сброшено (сторона {_side_label(payload.get('side'))})"
  if event_type == "hold_expired":
    return f"{_point_name(db, payload.get('point_id'))}: удержание прервано (dead-man, {_side_label(payload.get('side'))})"
  if event_type == "point_hold_ready":
    return f"{_point_name(db, payload.get('point_id'))}: 10 мин удержания — можно подрывать ({_side_label(payload.get('side'))})"
  if event_type == "point_capture":
    return f"{_point_name(db, payload.get('point_id'))}: захвачена ({_side_label(payload.get('side'))})"

  if event_type == "point_detonate":
    return f"{_point_name(db, payload.get('point_id'))}: пост подорван ({_side_label(payload.get('side'))})"
  if event_type == "point_admin_confirm":
    return f"{_point_name(db, payload.get('point_id'))}: пост подтверждён штабом"

  if event_type == "film_breach":
    return f"{_cache_name(db, payload.get('cache_id'))}: видеоотчёт вскрытия плёнки ({_side_label(payload.get('side'))})"
  if event_type == "deliver_report":
    return f"{_cache_name(db, payload.get('cache_id'))}: фотоотчёт доставки на базу ({_side_label(payload.get('side'))})"
  if event_type == "stage2_issued":
    name = _cache_name(db, payload.get("cache_id"))
    code = payload.get("code")
    lat = payload.get("lat")
    lon = payload.get("lon")
    parts = [f"Новая цель: {name}"]
    if code:
      parts.append(f"код {code}")
    if lat is not None and lon is not None:
      parts.append(f"координаты {lat:.6f}, {lon:.6f}")
    return " · ".join(parts)
  if event_type == "loot_deliver":
    return f"{_cache_name(db, payload.get('cache_id'))}: ящик сдан на базу ({_side_label(payload.get('side'))})"
  if event_type == "cache_delivery_confirm":
    return f"{_cache_name(db, payload.get('cache_id'))}: доставка подтверждена штабом"
  if event_type == "cache_admin_confirm":
    return f"{_cache_name(db, payload.get('cache_id'))}: схрон подтверждён штабом"

  if event_type == "cache_hold_start":
    return f"{_cache_name(db, payload.get('cache_id'))}: удержание схрона ({_side_label(payload.get('side'))})"
  if event_type == "cache_hold_ready":
    return f"{_cache_name(db, payload.get('cache_id'))}: схрон готов к подрыву ({_side_label(payload.get('side'))})"
  if event_type == "cache_hold_leave":
    return f"{_cache_name(db, payload.get('cache_id'))}: удержание схрона сброшено"
  if event_type == "cache_hold_expired":
    return f"{_cache_name(db, payload.get('cache_id'))}: удержание схрона прервано"

  return None


def _event_visible_for_side(event_type: str, payload: dict, side: str) -> bool:
  if event_type == "admin_broadcast":
    target = payload.get("target_side", "ALL")
    return target in ("ALL", side)
  return True


def build_commander_feed(db: Session, side: str, limit: int = 60) -> list[dict]:
  items: list[dict] = []
  scenario_id = get_active_scenario_id(db)
  for entry in (
    db.query(EventLog)
    .filter(EventLog.scenario_id == scenario_id)
    .order_by(EventLog.id.desc())
    .limit(200)
    .all()
  ):
    try:
      payload = json.loads(entry.payload or "{}")
    except json.JSONDecodeError:
      payload = {}

    if not _event_visible_for_side(entry.event_type, payload, side):
      continue

    text = format_event_text(db, entry.event_type, payload)
    if not text:
      continue

    items.append(
      {
        "id": entry.id,
        "created_at": entry.created_at.isoformat(),
        "event_type": entry.event_type,
        "text": text,
        "is_broadcast": entry.event_type == "admin_broadcast",
      }
    )
    if len(items) >= limit:
      break

  return list(reversed(items))
