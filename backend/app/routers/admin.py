import csv
import gzip
import io
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.game_kml_loader import apply_game_objects, load_kmz_dir_into_db
from app.kmz_parser import parse_kml_bytes, parse_kmz_file
from app.models import Cache, EventLog, FieldOrder, GameState, Landmark, Point, Stage2Assignment, User
from app.schemas import (
  AdminActionResponse,
  AdminCacheConfirmBody,
  BulkMapEnabledRequest,
  BroadcastRequest,
  FieldOrderOut,
  GameSettingsOut,
  GameSettingsUpdate,
  GpsCalibrateRequest,
  MapCacheCreate,
  MapCacheUpdate,
  MapLandmarkCreate,
  MapLandmarkUpdate,
  MapObjectOut,
  MapPointCreate,
  MapPointUpdate,
  MertvyakUpdate,
  MovementTracksResponse,
  Stage2AssignmentItem,
  Stage1CodeUpdate,
  Stage2MissionUpdate,
  Stage2MissionItem,
  ScoreBreakdownResponse,
  SideScoreBreakdown,
  StatusResponse,
)
from app.services import map_edit_service
from app.services.movement_track_service import current_session_tracks, session_track_rows
from app.point_codes import stage1_point_code
from app.qr_tokens import ensure_cache_qr_token, ensure_point_qr_token, qr_entry_url
from app.services.capture_settings import (
  capture_distance_disabled,
  capture_radius_m,
  gps_accuracy_bonus_max_m,
  gps_lat_offset,
  gps_lon_offset,
  gps_min_accuracy_for_capture_m,
  point_capture_seconds,
  point_hold_ping_seconds,
  post_hold_ping_seconds,
  post_hold_seconds,
  stage1_recapturable,
)
from app.services.engineer_pool_service import list_pool_engineers, sync_engineer_pool
from app.services.field_order_service import order_to_out
from app.services.game_service import get_or_create_game_state, log_event, pause_game, reset_game, set_stage, start_game
from app.services.stage1_schedule_service import (
  get_active_kt_numbers,
  get_stage1_phase,
  next_stage1_slot,
  serialize_hold_slots,
  stage1_hold_slots,
  start_stage1_slot,
)
from app.services.stage2_assignment_service import (
  enable_stage2_now,
  issue_next_assignment,
)
from app.services.hold_service import force_release_hold, refresh_active_hold_progress
from app.services.scoring import calculate_score_breakdown
from app.services.status_service import build_status_response
from app.routers import ws

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status", response_model=StatusResponse)
async def admin_status(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Статус для админ-карты: на этапе 2 видны все ящики, не только выданные."""
  for packet in refresh_active_hold_progress(db):
    await ws.broadcast_hold_update(packet)
  return build_status_response(
    db,
    stage2_player_view=False,
    viewer_role="admin",
    include_scores=True,
  )


@router.get("/scores/breakdown", response_model=ScoreBreakdownResponse)
def admin_score_breakdown(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  game = get_or_create_game_state(db)
  bd = calculate_score_breakdown(db, game)
  return ScoreBreakdownResponse(
    score_a=bd.score_a,
    score_b=bd.score_b,
    breakdown_a=SideScoreBreakdown(
      hold=bd.side_a.hold,
      captures=bd.side_a.captures,
      loot_breach=bd.side_a.loot_breach,
      loot_deliver=bd.side_a.loot_deliver,
      posts=bd.side_a.posts,
      caches=bd.side_a.caches,
    ),
    breakdown_b=SideScoreBreakdown(
      hold=bd.side_b.hold,
      captures=bd.side_b.captures,
      loot_breach=bd.side_b.loot_breach,
      loot_deliver=bd.side_b.loot_deliver,
      posts=bd.side_b.posts,
      caches=bd.side_b.caches,
    ),
  )


@router.post("/game/start", response_model=AdminActionResponse)
async def admin_start_game(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  state = start_game(db)
  await ws.broadcast_game_state(state.status)
  return AdminActionResponse(ok=True, message="Игра запущена. Запустите слот вручную.")


@router.post("/game/pause", response_model=AdminActionResponse)
async def admin_pause_game(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    state = pause_game(db)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  await ws.broadcast_game_state(state.status)
  return AdminActionResponse(ok=True, message="Игра на паузе — захват заблокирован")


@router.post("/game/reset", response_model=AdminActionResponse)
async def admin_reset_game(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  state = reset_game(db)
  await ws.broadcast_game_state(state.status)
  return AdminActionResponse(ok=True, message="Игра сброшена: этап 1, счёт и захваты обнулены")


@router.post("/game/stage/{stage}", response_model=AdminActionResponse)
async def admin_set_stage(
  stage: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    set_stage(db, stage)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc

  from app.kmz_parser import STAGE_LABELS

  label = STAGE_LABELS.get(stage, f"Этап {stage}")
  await ws.broadcast_admin_event({"e": "stage_change", "t": str(stage)})
  return AdminActionResponse(ok=True, message=f"Этап {stage}: {label}")


@router.post("/hold/force-release/{point_id}", response_model=AdminActionResponse)
async def admin_force_release(
  point_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  session = force_release_hold(db, point_id)
  if session is None:
    raise HTTPException(status_code=404, detail="Нет активного удержания")
  await ws.broadcast_hold_update({"e": "hold_leave", "p_id": point_id, "t": session.side})
  return AdminActionResponse(ok=True, message=f"Удержание точки {point_id} сброшено")


@router.post("/cache/{cache_id}/confirm", response_model=AdminActionResponse)
async def admin_cache_confirm(
  cache_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
  body: AdminCacheConfirmBody | None = None,
):
  """Подтверждение уничтожения — только админ. Для лута этапа 2 можно подтвердить без видео в системе."""
  body = body or AdminCacheConfirmBody()
  cache = db.query(Cache).filter(Cache.id == cache_id).first()
  if cache is None:
    raise HTTPException(status_code=404, detail="Схрон не найден")
  if cache.admin_confirmed:
    raise HTTPException(status_code=400, detail="Уже подтверждён")

  if not cache.destroyed:
    if cache.cache_kind != "film_loot":
      raise HTTPException(status_code=400, detail="Схрон ещё не подорван")
    if not body.side:
      raise HTTPException(
        status_code=400,
        detail="Укажите сторону (A или B) для подтверждения вскрытия без видео в системе",
      )
    from datetime import datetime

    cache.destroyed = True
    cache.destroyed_at = datetime.utcnow()
    cache.destroyed_by_side = body.side
    log_event(
      db,
      "film_breach",
      {"cache_id": cache_id, "side": body.side, "bonus": 0, "manual_admin": True},
    )

  cache.admin_confirmed = True
  log_event(db, "cache_admin_confirm", {"cache_id": cache_id, "side": cache.destroyed_by_side})
  db.commit()
  await ws.broadcast_admin_event({"e": "cache_confirmed", "p_id": cache_id, "t": cache.destroyed_by_side})
  return AdminActionResponse(ok=True, message=f"{cache.name}: вскрытие подтверждено")


@router.post("/cache/{cache_id}/confirm-delivery", response_model=AdminActionResponse)
async def admin_cache_confirm_delivery(
  cache_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
  body: AdminCacheConfirmBody | None = None,
):
  """Подтверждение доставки на базу — только админ. Можно без фото в системе."""
  from app.services.scoring import FILM_DELIVER_BONUS

  body = body or AdminCacheConfirmBody()
  cache = db.query(Cache).filter(Cache.id == cache_id).first()
  if cache is None:
    raise HTTPException(status_code=404, detail="Схрон не найден")
  if cache.cache_kind != "film_loot":
    raise HTTPException(status_code=400, detail="Подтверждение доставки только для лута этапа 2")
  if cache.delivered_at:
    raise HTTPException(status_code=400, detail="Доставка уже подтверждена")
  if not cache.destroyed:
    raise HTTPException(status_code=400, detail="Плёнка ещё не вскрыта")

  from datetime import datetime

  if not cache.delivery_reported_at:
    if not body.side:
      raise HTTPException(
        status_code=400,
        detail="Укажите сторону (A или B) для подтверждения доставки без фото в системе",
      )
    now = datetime.utcnow()
    cache.delivery_reported_at = now
    cache.delivered_by_side = body.side
    log_event(
      db,
      "deliver_report",
      {"cache_id": cache_id, "side": body.side, "manual_admin": True},
    )

  now = datetime.utcnow()
  cache.delivered_at = now
  if not cache.delivered_by_side:
    cache.delivered_by_side = cache.destroyed_by_side
  log_event(
    db,
    "loot_deliver",
    {"cache_id": cache_id, "side": cache.delivered_by_side, "bonus": FILM_DELIVER_BONUS},
  )
  log_event(db, "cache_delivery_confirm", {"cache_id": cache_id, "side": cache.delivered_by_side})
  db.commit()
  await ws.broadcast_admin_event(
    {"e": "cache_delivery_confirmed", "p_id": cache_id, "t": cache.delivered_by_side}
  )
  return AdminActionResponse(ok=True, message=f"{cache.name}: доставка подтверждена")


@router.post("/point/{point_id}/confirm", response_model=AdminActionResponse)
async def admin_point_confirm(
  point_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Подтверждение поста после видеоотчёта в ТГ (этап 3)."""
  point = db.query(Point).filter(Point.id == point_id).first()
  if point is None:
    raise HTTPException(status_code=404, detail="Пост не найден")
  if not point.destroyed:
    raise HTTPException(status_code=400, detail="Пост ещё не подорван")
  if point.admin_confirmed:
    raise HTTPException(status_code=400, detail="Уже подтверждён")

  point.admin_confirmed = True
  log_event(db, "point_admin_confirm", {"point_id": point_id, "side": point.destroyed_by_side})
  await ws.broadcast_admin_event({"e": "point_confirmed", "p_id": point_id, "t": point.destroyed_by_side})
  return AdminActionResponse(ok=True, message=f"{point.name}: подтверждён, пост выключен")


@router.post("/broadcast", response_model=AdminActionResponse)
async def admin_broadcast(
  body: BroadcastRequest,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Сообщение для командования одной или обеих сторон."""
  log_event(
    db,
    "admin_broadcast",
    {"message": body.message.strip(), "target_side": body.target_side},
  )
  await ws.broadcast_admin_event(
    {
      "e": "admin_broadcast",
      "t": body.target_side,
      "data": {"message": body.message.strip()},
    }
  )
  target = {"A": "ЛК", "B": "СБГ", "ALL": "обе стороны"}.get(body.target_side, body.target_side)
  return AdminActionResponse(ok=True, message=f"Сообщение отправлено: {target}")


@router.post("/kmz/import", response_model=AdminActionResponse)
async def admin_kmz_import(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
  file: UploadFile = File(...),
):
  content = await file.read()
  filename = file.filename or ""

  if filename.lower().endswith(".kml"):
    points, caches, landmarks = parse_kml_bytes(content, source_name=filename)
  else:
    points, caches, landmarks = parse_kmz_file(content, source_name=filename)

  if not points and not caches and not landmarks:
    raise HTTPException(status_code=400, detail="KML/KMZ не содержит объектов")

  n_pts, n_cch, n_lm = apply_game_objects(db, points, caches, landmarks, source=filename)
  return AdminActionResponse(
    ok=True,
    message=f"Импортировано: {n_pts} точек, {n_cch} схронов, {n_lm} баз/стартов",
  )


def _resolve_kmz_dir() -> Path | None:
  """Ищем каталог kmz/ в возможных местах (локальный dev и Docker-раскладка)."""
  import os

  env_dir = os.environ.get("KMZ_DIR")
  candidates: list[Path] = []
  if env_dir:
    candidates.append(Path(env_dir))
  here = Path(__file__).resolve()
  candidates.extend(
    [
      here.parents[2] / "kmz",  # /app/kmz  (docker: /app/app/routers -> /app)
      here.parents[3] / "kmz",  # <repo>/kmz  (локально: backend/app/routers -> <repo>)
      Path.cwd() / "kmz",
    ]
  )
  for c in candidates:
    if c.exists() and c.is_dir():
      return c
  return None


@router.post("/kml/reload", response_model=AdminActionResponse)
def admin_kml_reload(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Перезагрузка пресета из каталога kmz/ (Задача1 + ЛК + СБГ)."""
  kmz_dir = _resolve_kmz_dir()
  if kmz_dir is None:
    raise HTTPException(
      status_code=404,
      detail="Каталог kmz/ не найден. Смонтируйте ./kmz в контейнер (см. docker-compose.yml).",
    )
  result = load_kmz_dir_into_db(db, kmz_dir)
  if result is None:
    raise HTTPException(status_code=404, detail=f"KML не найден в {kmz_dir}")
  n_pts, n_cch, n_lm = result
  return AdminActionResponse(
    ok=True,
    message=f"Загружено из kmz/: {n_pts} КТ, {n_cch} схронов, {n_lm} баз/стартов",
  )


def _stage1_mission_item(point: Point, db: Session) -> dict:
  token = ensure_point_qr_token(point, db)
  db.flush()
  return {
    "id": point.id,
    "name": point.name,
    "lat": point.lat,
    "lon": point.lon,
    "code": stage1_point_code(point),
    "url": qr_entry_url(token),
    "enabled": point.enabled,
  }


def _stage2_mission_item(cache: Cache, db: Session) -> dict:
  token = ensure_cache_qr_token(cache, db)
  db.flush()
  return {
    "id": cache.id,
    "name": cache.name,
    "lat": cache.lat,
    "lon": cache.lon,
    "code": cache.detonation_code,
    "url": qr_entry_url(token),
    "enabled": cache.enabled,
  }


def _stage3_mertvyak_item(cache: Cache, db: Session) -> dict:
  token = ensure_cache_qr_token(cache, db)
  db.flush()
  return {
    "id": cache.id,
    "name": cache.name,
    "lat": cache.lat,
    "lon": cache.lon,
    "code": cache.detonation_code,
    "url": qr_entry_url(token),
    "enabled": cache.enabled,
  }


def _get_stage2_film_loot(db: Session, cache_id: int) -> Cache | None:
  return (
    db.query(Cache)
    .filter(Cache.id == cache_id, Cache.stage == 2, Cache.cache_kind == "film_loot")
    .first()
  )


def _get_stage1_point(db: Session, point_id: int) -> Point | None:
  return db.query(Point).filter(Point.id == point_id, Point.stage == 1).first()


@router.get("/stage1/mission", response_model=list[Stage2MissionItem])
def admin_stage1_mission(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """КТ этапа 1: QR, коды для табличек."""
  points = db.query(Point).filter(Point.stage == 1).order_by(Point.id).all()
  out = [_stage1_mission_item(p, db) for p in points]
  db.commit()
  return out


@router.patch("/stage1/mission/{point_id}", response_model=Stage2MissionItem)
def admin_stage1_mission_update_code(
  point_id: int,
  body: Stage1CodeUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  point = _get_stage1_point(db, point_id)
  if point is None:
    raise HTTPException(status_code=404, detail="КТ не найдена")
  point.detonation_code = body.code
  db.commit()
  db.refresh(point)
  log_event(db, "admin_stage1_code", {"point_id": point_id, "code": body.code})
  return _stage1_mission_item(point, db)


@router.get("/stage2/mission", response_model=list[Stage2MissionItem])
def admin_stage2_mission(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Координаты и коды всех 10 ящиков — раздача штабом обеим сторонам."""
  boxes = (
    db.query(Cache)
    .filter(Cache.stage == 2, Cache.cache_kind == "film_loot")
    .order_by(Cache.id)
    .all()
  )
  out = [_stage2_mission_item(c, db) for c in boxes]
  db.commit()
  return out


@router.get("/stage2/mission/{cache_id}", response_model=Stage2MissionItem)
def admin_stage2_mission_item(
  cache_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  cache = _get_stage2_film_loot(db, cache_id)
  if cache is None:
    raise HTTPException(status_code=404, detail="Ящик этапа 2 не найден")
  out = _stage2_mission_item(cache, db)
  db.commit()
  return out


@router.patch("/stage2/mission/{cache_id}", response_model=Stage2MissionItem)
def admin_stage2_mission_update(
  cache_id: int,
  body: Stage2MissionUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  cache = _get_stage2_film_loot(db, cache_id)
  if cache is None:
    raise HTTPException(status_code=404, detail="Ящик этапа 2 не найден")
  if body.code is not None:
    cache.detonation_code = body.code
    log_event(db, "admin_stage2_code", {"cache_id": cache_id, "code": body.code})
  if body.enabled is not None:
    cache.enabled = body.enabled
    log_event(db, "admin_stage2_enabled", {"cache_id": cache_id, "enabled": body.enabled})
  db.commit()
  db.refresh(cache)
  out = _stage2_mission_item(cache, db)
  db.commit()
  return out


@router.post("/stage2/issue", response_model=AdminActionResponse)
async def admin_stage2_issue_now(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Ручная выдача следующей цели этапа 2."""
  assignment = issue_next_assignment(db)
  if assignment is None:
    raise HTTPException(
      status_code=400,
      detail="Нет доступных ящиков: включите нужные точки в разделе «Ящики и коды»",
    )
  await ws.broadcast_stage2_issued(assignment.cache_id)
  cache = db.query(Cache).filter(Cache.id == assignment.cache_id).first()
  name = cache.name if cache else f"#{assignment.cache_id}"
  return AdminActionResponse(ok=True, message=f"Выдана цель: {name}")


@router.post("/stage2/enable", response_model=AdminActionResponse)
async def admin_stage2_enable_now(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Включить резервную Задачу-2 (параллельно с захватом КТ)."""
  enable_stage2_now(db)
  await ws.broadcast_settings_update()
  return AdminActionResponse(ok=True, message="Задача-2 включена. Включите нужные ящики и выдайте цель вручную.")


@router.post("/stage1/start-slot", response_model=AdminActionResponse)
async def admin_stage1_start_slot(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Запустить первый слот захвата КТ (этап 1)."""
  game = get_or_create_game_state(db)
  try:
    start_stage1_slot(db, game)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  kts = sorted(get_active_kt_numbers(game))
  log_event(db, "stage1_slot_start", {"slot": 0, "kts": kts})
  await ws.broadcast_settings_update()
  return AdminActionResponse(
    ok=True,
    message=f"Слот 1 запущен · активные КТ: {', '.join(str(k) for k in kts) or '—'}",
  )


@router.post("/stage1/next-slot", response_model=AdminActionResponse)
async def admin_stage1_next_slot(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Перейти к следующему слоту захвата КТ."""
  game = get_or_create_game_state(db)
  prev_idx = game.stage1_current_slot
  try:
    next_stage1_slot(db, game)
  except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
  phase = get_stage1_phase(game)
  if phase == "ended":
    log_event(db, "stage1_schedule_ended", {})
    await ws.broadcast_settings_update()
    return AdminActionResponse(ok=True, message="Все слоты этапа 1 завершены")
  kts = sorted(get_active_kt_numbers(game))
  slot_num = game.stage1_current_slot + 1
  log_event(db, "stage1_slot_next", {"slot": game.stage1_current_slot, "prev_slot": prev_idx, "kts": kts})
  await ws.broadcast_settings_update()
  return AdminActionResponse(
    ok=True,
    message=f"Слот {slot_num} · активные КТ: {', '.join(str(k) for k in kts) or '—'}",
  )


@router.get("/stage2/assignments", response_model=list[Stage2AssignmentItem])
def admin_stage2_assignments(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  rows = db.query(Stage2Assignment).order_by(Stage2Assignment.assigned_at.desc()).all()
  out: list[Stage2AssignmentItem] = []
  for row in rows:
    cache = db.query(Cache).filter(Cache.id == row.cache_id).first()
    out.append(
      Stage2AssignmentItem(
        id=row.id,
        cache_id=row.cache_id,
        cache_name=cache.name if cache else f"#{row.cache_id}",
        assigned_at=row.assigned_at,
        round_number=row.round_number,
        destroyed=bool(cache and cache.destroyed),
        destroyed_by_side=cache.destroyed_by_side if cache else None,
        delivered=bool(cache and cache.delivered_at),
        delivered_by_side=cache.delivered_by_side if cache else None,
      )
    )
  return out


@router.get("/stage3/mertvyaki", response_model=list[Stage2MissionItem])
def admin_stage3_mertvyaki(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  items = (
    db.query(Cache)
    .filter(Cache.stage == 3, Cache.cache_kind == "mertvyak")
    .order_by(Cache.id)
    .all()
  )
  out = [_stage3_mertvyak_item(c, db) for c in items]
  db.commit()
  return out


@router.patch("/stage3/mertvyaki/{cache_id}", response_model=Stage2MissionItem)
def admin_stage3_mertvyak_update(
  cache_id: int,
  body: MertvyakUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  cache = (
    db.query(Cache)
    .filter(Cache.id == cache_id, Cache.stage == 3, Cache.cache_kind == "mertvyak")
    .first()
  )
  if cache is None:
    raise HTTPException(status_code=404, detail="Мертвяк не найден")
  if body.enabled is not None:
    cache.enabled = body.enabled
  if body.code is not None:
    cache.detonation_code = body.code
  db.commit()
  db.refresh(cache)
  log_event(db, "admin_mertvyak", {"cache_id": cache_id, "enabled": cache.enabled})
  return _stage3_mertvyak_item(cache, db)


@router.get("/events")
def admin_events(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Последние события для журнала админки."""
  import json

  items = []
  for entry in db.query(EventLog).order_by(EventLog.id.desc()).limit(80).all():
    try:
      payload = json.loads(entry.payload or "{}")
    except json.JSONDecodeError:
      payload = {}
    summary = ", ".join(f"{k}={v}" for k, v in payload.items()) if payload else ""
    items.append(
      {
        "id": entry.id,
        "created_at": entry.created_at.isoformat(),
        "event_type": entry.event_type,
        "summary": summary,
      }
    )
  return items


@router.get("/export/logs")
def admin_export_logs(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(["id", "created_at", "event_type", "payload"])

  for entry in db.query(EventLog).order_by(EventLog.id).all():
    writer.writerow([entry.id, entry.created_at.isoformat(), entry.event_type, entry.payload])

  gz_buffer = io.BytesIO()
  with gzip.GzipFile(fileobj=gz_buffer, mode="wb") as gz:
    gz.write(output.getvalue().encode("utf-8-sig"))

  gz_buffer.seek(0)
  return StreamingResponse(
    gz_buffer,
    media_type="application/gzip",
    headers={"Content-Disposition": 'attachment; filename="event_log.csv.gz"'},
  )


@router.get("/export/engineers")
def admin_export_engineers(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(["side", "сторона", "логин", "пароль"])

  for user in list_pool_engineers(db):
    side_label = "ЛК" if user.side == "A" else "СБГ"
    writer.writerow([user.side or "", side_label, user.username, user.password_plain or ""])

  content = output.getvalue().encode("utf-8-sig")
  return StreamingResponse(
    io.BytesIO(content),
    media_type="text/csv; charset=utf-8",
    headers={"Content-Disposition": 'attachment; filename="engineers.csv"'},
  )


@router.get("/movement-tracks", response_model=MovementTracksResponse)
def admin_movement_tracks(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  return current_session_tracks(db)


@router.get("/export/movement-tracks")
def admin_export_movement_tracks(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  game = db.query(GameState).filter(GameState.id == 1).first()
  if game is None:
    game = GameState(id=1)
  rows = session_track_rows(db, game)

  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(
    ["game_session_id", "user_id", "username", "side", "label", "lat", "lon", "accuracy_m", "recorded_at"]
  )
  session_id = game.game_session_id or 1
  for row in rows:
    writer.writerow(
      [
        session_id,
        row.user_id,
        row.username,
        row.side,
        row.label,
        row.lat,
        row.lon,
        row.accuracy,
        row.recorded_at.isoformat(),
      ]
    )

  content = output.getvalue().encode("utf-8-sig")
  filename = f"movement_tracks_session_{session_id}.csv"
  return StreamingResponse(
    io.BytesIO(content),
    media_type="text/csv; charset=utf-8",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
  )


@router.get("/settings", response_model=GameSettingsOut)
def admin_get_settings(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  gs = db.query(GameState).filter(GameState.id == 1).first()
  a_target = gs.engineers_per_side_a if gs else 5
  b_target = gs.engineers_per_side_b if gs else 5
  count_a = db.query(User).filter(User.role == "engineer", User.side == "A", User.username.like("eng_a%")).count()
  count_b = db.query(User).filter(User.role == "engineer", User.side == "B", User.username.like("eng_b%")).count()
  return GameSettingsOut(
    engineers_per_side_a=a_target or 5,
    engineers_per_side_b=b_target or 5,
    engineers_count_a=count_a,
    engineers_count_b=count_b,
    capture_radius_m=capture_radius_m(gs) if gs else 10,
    disable_capture_distance=capture_distance_disabled(gs) if gs else False,
    stage1_recapturable=stage1_recapturable(gs),
    point_capture_seconds=point_capture_seconds(gs) if gs else 120,
    point_hold_ping_seconds=point_hold_ping_seconds(gs) if gs else 120,
    post_hold_seconds=post_hold_seconds(gs) if gs else 600,
    post_hold_ping_seconds=post_hold_ping_seconds(gs) if gs else 120,
    stage2_issue_interval_minutes=gs.stage2_issue_interval_minutes if gs else 60,
    stage2_issue_mode=gs.stage2_issue_mode if gs else "random",
    stage2_enabled=bool(gs.stage2_enabled) if gs else False,
    stage2_start_at=gs.stage2_start_at if gs else None,
    stage1_slot_minutes=gs.stage1_slot_minutes if gs else 120,
    stage1_hold_slots=stage1_hold_slots(gs) if gs else [[2, 3, 6, 8, 10], [4, 5, 9, 11, 12], [1, 3, 6, 7, 10]],
    gps_accuracy_bonus_max_m=gps_accuracy_bonus_max_m(gs),
    gps_min_accuracy_for_capture_m=gps_min_accuracy_for_capture_m(gs),
    gps_lat_offset=gps_lat_offset(gs),
    gps_lon_offset=gps_lon_offset(gs),
  )


@router.patch("/settings", response_model=GameSettingsOut)
async def admin_update_settings(
  body: GameSettingsUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  gs = db.query(GameState).filter(GameState.id == 1).first()
  if gs is None:
    gs = GameState(id=1)
    db.add(gs)
  gs.engineers_per_side_a = body.engineers_per_side_a
  gs.engineers_per_side_b = body.engineers_per_side_b
  gs.capture_radius_m = body.capture_radius_m
  gs.disable_capture_distance = body.disable_capture_distance
  gs.stage1_recapturable = body.stage1_recapturable
  gs.point_capture_seconds = body.point_capture_seconds
  gs.point_hold_ping_seconds = body.point_hold_ping_seconds
  gs.post_hold_seconds = body.post_hold_seconds
  gs.post_hold_ping_seconds = body.post_hold_ping_seconds
  gs.stage2_issue_interval_minutes = body.stage2_issue_interval_minutes
  gs.stage2_issue_mode = body.stage2_issue_mode
  if body.stage2_start_at is not None:
    gs.stage2_start_at = body.stage2_start_at
  gs.stage1_slot_minutes = body.stage1_slot_minutes
  if body.stage1_hold_slots is not None:
    gs.stage1_hold_slots_json = serialize_hold_slots(body.stage1_hold_slots)
  gs.gps_accuracy_bonus_max_m = body.gps_accuracy_bonus_max_m
  gs.gps_min_accuracy_for_capture_m = body.gps_min_accuracy_for_capture_m
  gs.gps_lat_offset = body.gps_lat_offset
  gs.gps_lon_offset = body.gps_lon_offset
  db.flush()
  sync_engineer_pool(db, purge_legacy=True)
  db.commit()

  await ws.broadcast_settings_update()

  count_a = db.query(User).filter(User.role == "engineer", User.side == "A", User.username.like("eng_a%")).count()
  count_b = db.query(User).filter(User.role == "engineer", User.side == "B", User.username.like("eng_b%")).count()
  return GameSettingsOut(
    engineers_per_side_a=gs.engineers_per_side_a,
    engineers_per_side_b=gs.engineers_per_side_b,
    engineers_count_a=count_a,
    engineers_count_b=count_b,
    capture_radius_m=capture_radius_m(gs),
    disable_capture_distance=capture_distance_disabled(gs),
    stage1_recapturable=stage1_recapturable(gs),
    point_capture_seconds=point_capture_seconds(gs),
    point_hold_ping_seconds=point_hold_ping_seconds(gs),
    post_hold_seconds=post_hold_seconds(gs),
    post_hold_ping_seconds=post_hold_ping_seconds(gs),
    stage2_issue_interval_minutes=gs.stage2_issue_interval_minutes,
    stage2_issue_mode=gs.stage2_issue_mode,
    stage2_enabled=bool(gs.stage2_enabled),
    stage2_start_at=gs.stage2_start_at,
    stage1_slot_minutes=gs.stage1_slot_minutes,
    stage1_hold_slots=stage1_hold_slots(gs),
    gps_accuracy_bonus_max_m=gps_accuracy_bonus_max_m(gs),
    gps_min_accuracy_for_capture_m=gps_min_accuracy_for_capture_m(gs),
    gps_lat_offset=gps_lat_offset(gs),
    gps_lon_offset=gps_lon_offset(gs),
  )


@router.post("/gps-calibrate", response_model=GameSettingsOut)
def admin_gps_calibrate(
  body: GpsCalibrateRequest,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Записать глобальное смещение GPS: true_coords - measured_coords."""
  gs = db.query(GameState).filter(GameState.id == 1).first()
  if gs is None:
    gs = GameState(id=1)
    db.add(gs)
  gs.gps_lat_offset = body.true_lat - body.measured_lat
  gs.gps_lon_offset = body.true_lon - body.measured_lon
  db.commit()

  count_a = db.query(User).filter(User.role == "engineer", User.side == "A", User.username.like("eng_a%")).count()
  count_b = db.query(User).filter(User.role == "engineer", User.side == "B", User.username.like("eng_b%")).count()
  return GameSettingsOut(
    engineers_per_side_a=gs.engineers_per_side_a or 5,
    engineers_per_side_b=gs.engineers_per_side_b or 5,
    engineers_count_a=count_a,
    engineers_count_b=count_b,
    capture_radius_m=capture_radius_m(gs),
    disable_capture_distance=capture_distance_disabled(gs),
    stage1_recapturable=stage1_recapturable(gs),
    point_capture_seconds=point_capture_seconds(gs),
    point_hold_ping_seconds=point_hold_ping_seconds(gs),
    post_hold_seconds=post_hold_seconds(gs),
    post_hold_ping_seconds=post_hold_ping_seconds(gs),
    stage2_issue_interval_minutes=gs.stage2_issue_interval_minutes,
    stage2_issue_mode=gs.stage2_issue_mode,
    stage2_enabled=bool(gs.stage2_enabled),
    stage2_start_at=gs.stage2_start_at,
    stage1_slot_minutes=gs.stage1_slot_minutes,
    stage1_hold_slots=stage1_hold_slots(gs),
    gps_accuracy_bonus_max_m=gps_accuracy_bonus_max_m(gs),
    gps_min_accuracy_for_capture_m=gps_min_accuracy_for_capture_m(gs),
    gps_lat_offset=gps_lat_offset(gs),
    gps_lon_offset=gps_lon_offset(gs),
  )


def _map_edit_http_error(exc: Exception) -> HTTPException:
  if isinstance(exc, LookupError):
    return HTTPException(status_code=404, detail=str(exc))
  return HTTPException(status_code=400, detail=str(exc))


def _point_out(p: Point) -> MapObjectOut:
  return MapObjectOut(id=p.id, name=p.name, lat=p.lat, lon=p.lon, stage=p.stage, kind="point")


def _cache_out(c: Cache) -> MapObjectOut:
  return MapObjectOut(
    id=c.id,
    name=c.name,
    lat=c.lat,
    lon=c.lon,
    stage=c.stage,
    cache_kind=c.cache_kind,
    team_side=c.team_side,
    kind="cache",
  )


def _landmark_out(lm: Landmark) -> MapObjectOut:
  return MapObjectOut(
    id=lm.id,
    name=lm.name,
    lat=lm.lat,
    lon=lm.lon,
    kind=lm.kind,
    team_side=lm.team_side,
  )


async def _broadcast_map_update() -> None:
  await ws.broadcast_admin_event({"e": "map_update"})


@router.post("/map/bulk-enabled", response_model=AdminActionResponse)
async def admin_bulk_map_enabled(
  body: BulkMapEnabledRequest,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  parts: list[str] = []
  if body.points:
    n = db.query(Point).update({Point.enabled: body.enabled}, synchronize_session=False)
    parts.append(f"КТ: {n}")
  if body.caches:
    n = db.query(Cache).update({Cache.enabled: body.enabled}, synchronize_session=False)
    parts.append(f"схроны: {n}")
  if body.landmarks:
    n = db.query(Landmark).update({Landmark.enabled: body.enabled}, synchronize_session=False)
    parts.append(f"базы/старты: {n}")
  log_event(
    db,
    "admin_map_bulk_enabled",
    {"enabled": body.enabled, "points": body.points, "caches": body.caches, "landmarks": body.landmarks},
  )
  db.commit()
  await _broadcast_map_update()
  verb = "показаны на карте" if body.enabled else "скрыты с карты"
  return AdminActionResponse(ok=True, message=f"Объекты {verb}: {', '.join(parts)}")


@router.post("/map/wipe", response_model=AdminActionResponse)
async def admin_map_wipe(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    n_pts, n_cch, n_lm = map_edit_service.wipe_all_objects(db)
  except ValueError as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return AdminActionResponse(
    ok=True,
    message=f"Удалено: {n_pts} КТ/постов, {n_cch} схронов, {n_lm} баз/стартов",
  )


@router.patch("/map/points/{point_id}", response_model=MapObjectOut)
async def admin_map_update_point(
  point_id: int,
  body: MapPointUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    point = map_edit_service.update_point(
      db,
      point_id,
      lat=body.lat,
      lon=body.lon,
      name=body.name,
    )
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _point_out(point)


@router.post("/map/points", response_model=MapObjectOut)
async def admin_map_create_point(
  body: MapPointCreate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    point = map_edit_service.create_point(
      db,
      lat=body.lat,
      lon=body.lon,
      stage=body.stage,
      name=body.name,
    )
  except ValueError as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _point_out(point)


@router.delete("/map/points/{point_id}", response_model=AdminActionResponse)
async def admin_map_delete_point(
  point_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    map_edit_service.delete_point(db, point_id)
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return AdminActionResponse(ok=True, message="Точка удалена")


@router.patch("/map/caches/{cache_id}", response_model=MapObjectOut)
async def admin_map_update_cache(
  cache_id: int,
  body: MapCacheUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    cache = map_edit_service.update_cache(
      db,
      cache_id,
      lat=body.lat,
      lon=body.lon,
      name=body.name,
      team_side=body.team_side,
    )
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _cache_out(cache)


@router.post("/map/caches", response_model=MapObjectOut)
async def admin_map_create_cache(
  body: MapCacheCreate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    cache = map_edit_service.create_cache(
      db,
      lat=body.lat,
      lon=body.lon,
      stage=body.stage,
      cache_kind=body.cache_kind,
      team_side=body.team_side,
      name=body.name,
      loot_variant=body.loot_variant or "film_passage",
    )
  except ValueError as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _cache_out(cache)


@router.delete("/map/caches/{cache_id}", response_model=AdminActionResponse)
async def admin_map_delete_cache(
  cache_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    map_edit_service.delete_cache(db, cache_id)
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return AdminActionResponse(ok=True, message="Схрон удалён")


@router.patch("/map/landmarks/{landmark_id}", response_model=MapObjectOut)
async def admin_map_update_landmark(
  landmark_id: int,
  body: MapLandmarkUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    landmark = map_edit_service.update_landmark(
      db,
      landmark_id,
      lat=body.lat,
      lon=body.lon,
      name=body.name,
      kind=body.kind,
      team_side=body.team_side,
    )
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _landmark_out(landmark)


@router.post("/map/landmarks", response_model=MapObjectOut)
async def admin_map_create_landmark(
  body: MapLandmarkCreate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    landmark = map_edit_service.create_landmark(
      db,
      lat=body.lat,
      lon=body.lon,
      kind=body.kind,
      team_side=body.team_side,
      name=body.name,
    )
  except ValueError as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return _landmark_out(landmark)


@router.delete("/map/landmarks/{landmark_id}", response_model=AdminActionResponse)
async def admin_map_delete_landmark(
  landmark_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  try:
    map_edit_service.delete_landmark(db, landmark_id)
  except (ValueError, LookupError) as exc:
    raise _map_edit_http_error(exc) from exc
  await _broadcast_map_update()
  return AdminActionResponse(ok=True, message="Ориентир удалён")


@router.get("/orders", response_model=list[FieldOrderOut])
def admin_list_orders(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
  side: str | None = None,
  limit: int = 50,
):
  q = db.query(FieldOrder)
  if side in ("A", "B"):
    q = q.filter(FieldOrder.side == side)
  rows = q.order_by(FieldOrder.created_at.desc()).limit(min(limit, 100)).all()
  return [FieldOrderOut(**order_to_out(r)) for r in rows]
