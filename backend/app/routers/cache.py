from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_engineer
from app.database import get_db
from app.geo_utils import effective_fence_radius_m, haversine_m
from app.models import Cache, ChatMessage, User
from app.services.objective_video_chat import publish_objective_video_chat, side_label
from app.routers import ws
from app.schemas import CacheCodeRequest, DeliverRequest, DetonateRequest
from app.services.capture_settings import capture_distance_disabled, capture_radius_m, gps_accuracy_bonus_max_m
from app.services.chat_media import save_chat_media
from app.services.game_service import assert_game_running, get_or_create_game_state, log_event
from app.services.scenario_service import get_active_scenario_id
from app.services.scoring import FILM_BREACH_BONUS, FILM_DELIVER_BONUS
from app.services.stage2_assignment_service import is_cache_issued, is_stage2_active

router = APIRouter(prefix="/api/cache", tags=["cache"])


def _side_label(side: str) -> str:
  return "ЛК" if side == "A" else "СБГ"


def _require_side(user: User, side: str) -> None:
  if user.side and user.side != side:
    raise HTTPException(status_code=403, detail="Сторона не совпадает с учётной записью")


def _get_film_loot(db: Session, cache_id: int) -> Cache:
  cache = db.query(Cache).filter(Cache.id == cache_id).first()
  if cache is None:
    raise HTTPException(status_code=404, detail="Объект не найден")
  if cache.cache_kind != "film_loot" or cache.stage != 2:
    raise HTTPException(status_code=400, detail="Операция только для ящиков этапа 2")
  return cache


def _assert_stage2_loot_active(db: Session, cache: Cache) -> None:
  game = get_or_create_game_state(db)
  try:
    assert_game_running(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  if not is_stage2_active(game):
    raise HTTPException(status_code=400, detail="Задача-2 ещё не началась")
  if not is_cache_issued(db, cache.id):
    raise HTTPException(status_code=403, detail="Цель ещё не выдана")


def _check_geofence(
  game,
  cache: Cache,
  lat: float | None,
  lon: float | None,
  accuracy: float | None = None,
) -> None:
  if capture_distance_disabled(game) or lat is None or lon is None:
    return
  dist = haversine_m(lat, lon, cache.lat, cache.lon)
  fence_m = effective_fence_radius_m(capture_radius_m(game), accuracy, gps_accuracy_bonus_max_m(game))
  if dist > fence_m:
    raise HTTPException(
      status_code=400,
      detail=f"Подойдите к объекту (сейчас {int(dist)}м, нужно ≤{fence_m}м)",
    )


def _verify_loot_code(cache: Cache, code: str) -> None:
  if code != cache.detonation_code:
    raise HTTPException(status_code=400, detail="Неверный код")


def _require_qr_token(cache: Cache, qr_token: str) -> None:
  if not cache.qr_token or qr_token != cache.qr_token:
    raise HTTPException(status_code=403, detail="Откройте объект по QR-ссылке с таблички")


def _apply_film_breach(db: Session, cache: Cache, side: str) -> None:
  if cache.destroyed:
    who = cache.destroyed_by_side or "?"
    raise HTTPException(status_code=400, detail=f"Плёнка уже вскрыта стороной {who}")

  cache.destroyed = True
  cache.destroyed_at = datetime.utcnow()
  cache.destroyed_by_side = side
  cache.admin_confirmed = False
  cache.code_verified_at = None
  cache.code_verified_by_side = None
  cache.code_verified_qr_token = None

  log_event(
    db,
    "film_breach",
    {"cache_id": cache.id, "side": side, "bonus": FILM_BREACH_BONUS},
  )


@router.post("/breach-code")
def breach_code(
  body: CacheCodeRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 2 · проход с плёнкой: проверка кода перед подрывом."""
  if body.side not in ("A", "B"):
    raise HTTPException(status_code=400, detail="Укажите сторону A или B")
  _require_side(user, body.side)

  cache = _get_film_loot(db, body.cache_id)
  _assert_stage2_loot_active(db, cache)
  _require_qr_token(cache, body.qr_token)
  if (cache.loot_variant or "film_passage") != "film_passage":
    raise HTTPException(status_code=400, detail="Этот ящик открывается без подрыва — используйте unlock-code")
  if cache.destroyed:
    raise HTTPException(status_code=400, detail="Плёнка уже вскрыта")

  game = get_or_create_game_state(db)
  _check_geofence(game, cache, body.lat, body.lon, body.accuracy)
  _verify_loot_code(cache, body.code)

  now = datetime.utcnow()
  cache.code_verified_at = now
  cache.code_verified_by_side = body.side
  cache.code_verified_qr_token = body.qr_token
  log_event(db, "film_code_verified", {"cache_id": cache.id, "side": body.side})
  db.commit()

  return {
    "ok": True,
    "message": "Код принят. Загрузите видео объективного контроля подрыва.",
    "next_step": "film_report",
  }


@router.post("/unlock-code")
async def unlock_code(
  body: CacheCodeRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 2 · ящик с табличкой: код → можно забирать."""
  if body.side not in ("A", "B"):
    raise HTTPException(status_code=400, detail="Укажите сторону A или B")
  _require_side(user, body.side)

  cache = _get_film_loot(db, body.cache_id)
  _assert_stage2_loot_active(db, cache)
  _require_qr_token(cache, body.qr_token)
  if (cache.loot_variant or "film_passage") != "box_direct":
    raise HTTPException(status_code=400, detail="Для этого ящика нужен подрыв плёнки")
  if cache.destroyed:
    who = cache.destroyed_by_side or "?"
    raise HTTPException(status_code=400, detail=f"Ящик уже открыт стороной {who}")

  game = get_or_create_game_state(db)
  _check_geofence(game, cache, body.lat, body.lon, body.accuracy)
  _verify_loot_code(cache, body.code)

  cache.destroyed = True
  cache.destroyed_at = datetime.utcnow()
  cache.destroyed_by_side = body.side
  cache.admin_confirmed = False
  log_event(db, "loot_unlock", {"cache_id": cache.id, "side": body.side})
  db.commit()
  await ws.broadcast_admin_event({"e": "cache_detonate", "p_id": cache.id, "t": body.side})

  return {
    "ok": True,
    "message": "Код принят. Заберите ящик и доставьте на базу.",
    "next_step": "deliver",
  }


@router.post("/detonate")
def detonate_cache(
  body: DetonateRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  cache = db.query(Cache).filter(Cache.id == body.cache_id).first()
  if cache is None:
    raise HTTPException(status_code=404, detail="Объект не найден")

  game = get_or_create_game_state(db)
  try:
    assert_game_running(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  if cache.cache_kind == "film_loot":
    raise HTTPException(
      status_code=400,
      detail="Для ящиков этапа 2 используйте QR-страницу: код → подрыв → видео",
    )
  if cache.cache_kind == "mertvyak":
    raise HTTPException(status_code=400, detail="Мертвяки настраиваются в админке")
  if cache.stage != game.current_stage:
    raise HTTPException(
      status_code=400,
      detail=f"Активен этап {game.current_stage}, объект на этапе {cache.stage}",
    )
  raise HTTPException(status_code=400, detail="Объект не поддерживает детонацию")


async def _publish_film_report_chat(
  db: Session,
  *,
  user: User,
  side: str,
  cache: Cache,
  media_type: str,
  media_path: str,
  media_filename: str,
) -> list[ChatMessage]:
  text = (
    f"Этап 2 · {cache.name}\n"
    f"Сторона {side_label(side)} · инженер {user.username}\n"
    f"Видео объективного контроля подрыва плёнки."
  )
  msg = await publish_objective_video_chat(
    db,
    user=user,
    side=side,
    text=text,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )
  return [msg]


@router.post("/film-report")
async def film_report(
  cache_id: Annotated[int, Form()],
  side: Annotated[str, Form()],
  lat: Annotated[float, Form()],
  lon: Annotated[float, Form()],
  qr_token: Annotated[str, Form()],
  file: Annotated[UploadFile, File(...)],
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 2: подрыв плёнки — только после проверки кода, с видеофиксацией."""
  if side not in ("A", "B"):
    raise HTTPException(status_code=400, detail="Укажите сторону A или B")
  _require_side(user, side)

  cache = _get_film_loot(db, cache_id)
  _assert_stage2_loot_active(db, cache)
  _require_qr_token(cache, qr_token)
  if (cache.loot_variant or "film_passage") != "film_passage":
    raise HTTPException(status_code=400, detail="Для этого ящика подрыв не требуется")

  game = get_or_create_game_state(db)
  if (
    not cache.code_verified_at
    or cache.code_verified_by_side != side
    or cache.code_verified_qr_token != qr_token
  ):
    raise HTTPException(status_code=400, detail="Сначала введите и подтвердите код от штаба")
  if cache.destroyed:
    raise HTTPException(status_code=400, detail="Плёнка уже вскрыта")

  media_type, media_path, media_filename = await save_chat_media(file)
  if media_type != "video":
    raise HTTPException(status_code=400, detail="Загрузите видео объективного контроля (MP4/WebM/MOV)")

  _apply_film_breach(db, cache, side)
  await _publish_film_report_chat(
    db,
    user=user,
    side=side,
    cache=cache,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )
  db.commit()
  await ws.broadcast_admin_event({"e": "cache_detonate", "p_id": cache.id, "t": side})

  return {
    "ok": True,
    "bonus": FILM_BREACH_BONUS,
    "cache_id": cache.id,
    "next_step": "deliver",
    "message": (
      "Подрыв зафиксирован, видеоотчёт в чате командования. "
      "Заберите ящик, доставьте на базу и загрузите фото."
    ),
  }


async def _publish_deliver_report_chat(
  db: Session,
  *,
  user: User,
  side: str,
  cache: Cache,
  media_type: str,
  media_path: str,
  media_filename: str,
) -> list[ChatMessage]:
  side_label = _side_label(side)
  text = (
    f"Этап 2 · {cache.name}\n"
    f"Сторона {side_label} · инженер {user.username}\n"
    f"Фото доставки ящика на базу для подтверждения штабом."
  )
  msg = ChatMessage(
    scenario_id=get_active_scenario_id(db),
    side=side,
    thread="cmd",
    sender_role=user.role,
    sender_username=user.username,
    text=text,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )
  db.add(msg)
  db.flush()
  await ws.broadcast_chat_event(
    {
      "e": "chat",
      "t": side,
      "thread": "cmd",
      "p_id": msg.id,
      "u": user.username,
      "r": user.role,
    }
  )
  return [msg]


@router.post("/deliver-report")
async def deliver_report(
  cache_id: Annotated[int, Form()],
  side: Annotated[str, Form()],
  lat: Annotated[float, Form()],
  lon: Annotated[float, Form()],
  qr_token: Annotated[str, Form()],
  file: Annotated[UploadFile, File(...)],
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 2: фотоотчёт доставки на базу."""
  if side not in ("A", "B"):
    raise HTTPException(status_code=400, detail="Укажите сторону A или B")
  _require_side(user, side)

  cache = _get_film_loot(db, cache_id)
  _assert_stage2_loot_active(db, cache)
  _require_qr_token(cache, qr_token)

  try:
    assert_game_running(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  if not cache.destroyed:
    raise HTTPException(status_code=400, detail="Сначала вскройте плёнку или введите код ящика")
  if cache.destroyed_by_side != side:
    raise HTTPException(status_code=403, detail="Ящик открыла другая сторона")
  if cache.delivered_at:
    raise HTTPException(status_code=400, detail="Ящик уже сдан на базу")
  if cache.delivery_reported_at:
    raise HTTPException(status_code=400, detail="Фотоотчёт доставки уже отправлен")

  media_type, media_path, media_filename = await save_chat_media(file)
  if media_type != "image":
    raise HTTPException(status_code=400, detail="Загрузите фото доставки на базу (JPEG/PNG/WebP)")

  now = datetime.utcnow()
  cache.delivery_reported_at = now
  cache.delivered_by_side = side
  log_event(db, "deliver_report", {"cache_id": cache.id, "side": side})
  await _publish_deliver_report_chat(
    db,
    user=user,
    side=side,
    cache=cache,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )
  db.commit()
  await ws.broadcast_admin_event({"e": "cache_deliver_report", "p_id": cache.id, "t": side})

  return {
    "ok": True,
    "message": "Фотоотчёт отправлен в чат командования. Ожидайте подтверждения штабом.",
  }


@router.post("/deliver")
def deliver_loot(
  body: DeliverRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  raise HTTPException(
    status_code=400,
    detail="Загрузите фото доставки на базу через /api/cache/deliver-report",
  )
