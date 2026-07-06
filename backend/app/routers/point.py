from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_engineer
from app.database import get_db
from app.geo_utils import effective_fence_radius_m, haversine_m
from app.models import Point, User
from app.routers import ws
from app.schemas import PointBeginCaptureRequest, PointDetonateRequest
from app.point_codes import stage1_point_code
from app.services.capture_settings import (
  capture_distance_disabled,
  capture_radius_m,
  gps_accuracy_bonus_max_m,
  stage1_recapturable,
)
from app.services.chat_media import save_chat_media
from app.services.game_service import get_or_create_game_state, log_event, assert_game_running
from app.services.hold_service import (
  POST_ALREADY_DESTROYED,
  POST_SBG_PASSIVE,
  confirm_hold,
  expire_hold_if_deadman_elapsed,
  hold_deadman_seconds_for_point,
  hold_elapsed_seconds,
  is_stage1_captured,
  leave_hold,
  require_point_hold_ready,
)
from app.services.objective_video_chat import publish_objective_video_chat, side_label
from app.services.scoring import POST_DESTROY_BONUS
from app.services.stage1_schedule_service import assert_stage1_capturable

router = APIRouter(prefix="/api/point", tags=["point"])


def _require_side(user: User, side: str) -> None:
  if user.side and user.side != side:
    raise HTTPException(status_code=403, detail="Сторона не совпадает с учётной записью")


def _check_point_geofence(
  game,
  point: Point,
  lat: float,
  lon: float,
  accuracy: float | None = None,
) -> None:
  if capture_distance_disabled(game):
    return
  dist = haversine_m(lat, lon, point.lat, point.lon)
  fence_m = effective_fence_radius_m(capture_radius_m(game), accuracy, gps_accuracy_bonus_max_m(game))
  if dist > fence_m:
    raise HTTPException(
      status_code=400,
      detail=f"Подойдите к точке (сейчас {int(dist)}м, нужно ≤{fence_m}м)",
    )


@router.post("/begin-capture")
async def begin_point_capture(
  body: PointBeginCaptureRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 1 / 3: код с таблички + нахождение в зоне → старт удержания."""
  _require_side(user, body.side)

  point = db.query(Point).filter(Point.id == body.point_id).first()
  if point is None:
    raise HTTPException(status_code=404, detail="Точка не найдена")

  game = get_or_create_game_state(db)
  try:
    assert_game_running(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  if point.destroyed:
    raise HTTPException(status_code=400, detail=POST_ALREADY_DESTROYED)

  is_stage1 = point.stage == 1 and game.current_stage != 3
  is_stage3_assault = point.stage == 3 and game.current_stage == 3

  if not is_stage1 and not is_stage3_assault:
    raise HTTPException(status_code=400, detail="Захват по коду недоступен на этом этапе")

  if is_stage3_assault:
    if body.side != "A":
      raise HTTPException(status_code=403, detail="Штурм постов ведёт только сторона ЛК")
  elif is_stage1:
    if is_stage1_captured(point):
      if point.side == body.side:
        raise HTTPException(status_code=400, detail="Точка уже под контролем вашей стороны")
      if not stage1_recapturable(game):
        raise HTTPException(status_code=400, detail="Точка уже захвачена")
    try:
      assert_stage1_capturable(point, game)
    except ValueError as exc:
      raise HTTPException(status_code=400, detail=str(exc)) from exc

  expected = stage1_point_code(point)
  if body.code != expected:
    raise HTTPException(status_code=400, detail="Неверный код")

  _check_point_geofence(game, point, body.lat, body.lon, body.accuracy)

  expire_hold_if_deadman_elapsed(db, body.point_id)
  try:
    session, _created = confirm_hold(
      db,
      body.point_id,
      body.side,
      user.id,
      allow_stage1_start=is_stage1,
      allow_stage3_start=is_stage3_assault,
    )
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  await ws.broadcast_hold_update({"e": "hold_start", "p_id": body.point_id, "t": body.side})

  message = (
    "Штурм начат. Подтверждайте удержание по таймеру."
    if is_stage3_assault
    else "Захват начат. Подтверждайте удержание по таймеру."
  )
  return {
    "ok": True,
    "session_id": session.id,
    "last_ping_at": session.last_ping_at,
    "hold_ready": session.hold_ready,
    "hold_elapsed_sec": hold_elapsed_seconds(session),
    "hold_deadman_seconds": hold_deadman_seconds_for_point(db, body.point_id),
    "message": message,
  }


@router.post("/post-film-report")
async def post_film_report(
  point_id: Annotated[int, Form()],
  side: Annotated[str, Form()],
  lat: Annotated[float, Form()],
  lon: Annotated[float, Form()],
  file: Annotated[UploadFile, File(...)],
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Этап 3: видео объективного контроля после удержания поста (только ЛК)."""
  if side != "A":
    raise HTTPException(status_code=403, detail="Штурм постов ведёт только сторона ЛК")
  _require_side(user, side)

  point = db.query(Point).filter(Point.id == point_id).first()
  if point is None:
    raise HTTPException(status_code=404, detail="Пост не найден")

  game = get_or_create_game_state(db)
  try:
    assert_game_running(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  if point.stage != 3 or game.current_stage != 3:
    raise HTTPException(status_code=400, detail="Видео ОК только для постов этапа 3")
  if point.destroyed:
    raise HTTPException(status_code=400, detail=POST_ALREADY_DESTROYED)

  try:
    require_point_hold_ready(db, point.id, side)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  _check_point_geofence(game, point, lat, lon)

  media_type, media_path, media_filename = await save_chat_media(file)
  if media_type != "video":
    raise HTTPException(status_code=400, detail="Загрузите видео объективного контроля (MP4/WebM/MOV)")

  leave_hold(db, point.id, side)

  point.destroyed = True
  point.destroyed_at = datetime.utcnow()
  point.destroyed_by_side = side
  point.admin_confirmed = False
  point.side = None

  text = (
    f"Этап 3 · {point.name}\n"
    f"Сторона {side_label(side)} · инженер {user.username}\n"
    f"Видео объективного контроля подрыва поста."
  )
  await publish_objective_video_chat(
    db,
    user=user,
    side=side,
    text=text,
    media_type=media_type,
    media_path=media_path,
    media_filename=media_filename,
  )

  log_event(
    db,
    "point_detonate",
    {"point_id": point.id, "side": side, "bonus": POST_DESTROY_BONUS},
  )
  db.commit()
  await ws.broadcast_admin_event({"e": "cache_detonate", "p_id": point.id, "t": side})

  return {
    "ok": True,
    "bonus": POST_DESTROY_BONUS,
    "point_id": point.id,
    "message": "Пост подорван. Видеоотчёт в чате командования. Ожидайте подтверждения штаба.",
  }


@router.post("/detonate")
async def detonate_point(
  body: PointDetonateRequest,
  db: Annotated[Session, Depends(get_db)],
  user: Annotated[User, Depends(require_engineer)],
):
  """Устарело: подрыв поста теперь через видео объективного контроля."""
  point = db.query(Point).filter(Point.id == body.point_id).first()
  if point is None:
    raise HTTPException(status_code=404, detail="Пост не найден")

  game = get_or_create_game_state(db)
  if point.stage == 3 and game.current_stage == 3:
    raise HTTPException(
      status_code=400,
      detail="Детонация кодом отключена. После удержания загрузите видео объективного контроля.",
    )

  raise HTTPException(status_code=400, detail="Детонация недоступна для этой точки")
