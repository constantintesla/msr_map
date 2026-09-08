from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.kmz_parser import STAGE_LABELS
from app.models import Cache, GameStatus, HoldSession, Landmark, Point
from app.schemas import CacheStatus, LandmarkStatus, PointStatus, StageInfo, StatusResponse
from app.config import settings
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
from app.services.game_service import get_or_create_game_state
from app.services.hold_service import hold_elapsed_seconds, is_stage1_captured
from app.services.scoring import calculate_scores, calculate_score_breakdown
from app.qr_tokens import qr_entry_url
from app.services.stage2_assignment_service import (
  get_active_stage2_cache_id,
  get_issued_cache_ids,
  is_stage2_active,
  stage2_next_issue_at,
)
from app.services.stage1_schedule_service import (
  get_active_kt_numbers,
  get_stage1_phase,
  is_point_capturable,
  kt_number_from_name,
  stage1_current_slot_index,
  stage1_hold_slots,
  stage1_slot_ends_at,
)


def _stage_counts(db: Session, scenario_id: int) -> list[StageInfo]:
  stages: list[StageInfo] = []
  for n in (1, 2, 3):
    pc = (
      db.query(func.count(Point.id))
      .filter(Point.scenario_id == scenario_id, Point.stage == n)
      .scalar()
      or 0
    )
    cc = (
      db.query(func.count(Cache.id))
      .filter(Cache.scenario_id == scenario_id, Cache.stage == n)
      .scalar()
      or 0
    )
    stages.append(
      StageInfo(
        stage=n,
        label=STAGE_LABELS.get(n, f"Этап {n}"),
        points_count=pc,
        caches_count=cc,
      )
    )
  return stages


def _map_point_stage(game) -> int:
  return 3 if game.current_stage == 3 else 1


def build_status_response(
  db: Session,
  *,
  stage2_player_view: bool = False,
  viewer_side: str | None = None,
  viewer_role: str | None = None,
  include_scores: bool = False,
) -> StatusResponse:
  """Статус для карты и командования."""
  del viewer_side
  game = get_or_create_game_state(db)
  scenario_id = game.id
  if include_scores:
    score_a, score_b = calculate_scores(db, game)
  else:
    score_a, score_b = None, None
  stage = game.current_stage
  stage2_on = is_stage2_active(game)
  map_point_stage = _map_point_stage(game)

  issued_ids = get_issued_cache_ids(db) if stage2_on else set()
  active_stage2_id = get_active_stage2_cache_id(db) if stage2_on else None

  show_stage1 = map_point_stage == 1
  stage1_phase = get_stage1_phase(game) if show_stage1 else None
  active_kts = sorted(get_active_kt_numbers(game)) if show_stage1 else []
  slot_idx = stage1_current_slot_index(game) if show_stage1 else -1
  slot_count = len(stage1_hold_slots(game)) if show_stage1 else 0
  current_slot_display = slot_idx if show_stage1 and stage1_phase == "hold" else None

  map_edit_preview = viewer_role == "admin" and game.status == GameStatus.IDLE.value

  points_out: list[PointStatus] = []
  point_query = db.query(Point).filter(Point.scenario_id == scenario_id, Point.enabled.is_(True))
  if not map_edit_preview:
    point_query = point_query.filter(Point.stage == map_point_stage)
  for point in point_query.order_by(Point.id).all():
    active = (
      db.query(HoldSession)
      .filter(HoldSession.point_id == point.id, HoldSession.active.is_(True))
      .first()
    )
    captured = is_stage1_captured(point)
    hold_ready = (active.hold_ready if active else False) or captured
    is_stage1_point = point.stage == 1
    kt_num = kt_number_from_name(point.name) if show_stage1 and is_stage1_point else None
    points_out.append(
      PointStatus(
        id=point.id,
        name=point.name,
        lat=point.lat,
        lon=point.lon,
        side=point.side,
        held_by=active.side if active else None,
        held_by_user_id=active.user_id if active else None,
        hold_started_at=active.started_at if active else None,
        last_ping_at=active.last_ping_at if active else None,
        hold_ready=hold_ready,
        hold_elapsed_sec=hold_elapsed_seconds(active) if active else 0,
        destroyed=point.destroyed,
        destroyed_by_side=point.destroyed_by_side,
        admin_confirmed=point.admin_confirmed,
        pending_admin=point.destroyed and not point.admin_confirmed,
        kt_number=kt_num,
        stage1_capturable=is_point_capturable(point, game) if show_stage1 and is_stage1_point else False,
        entry_url=qr_entry_url(point.qr_token) if point.qr_token else None,
      )
    )

  caches_out: list[CacheStatus] = []
  cache_query = db.query(Cache).filter(Cache.scenario_id == scenario_id)
  if map_edit_preview:
    pass
  elif stage == 3:
    cache_query = cache_query.filter(Cache.stage == 3)
  elif viewer_role == "admin":
    cache_query = cache_query.filter(
      (Cache.stage == stage) | ((Cache.stage == 2) & (Cache.cache_kind == "film_loot"))
    )
  elif stage2_on:
    cache_query = cache_query.filter(Cache.stage == 2)
  else:
    cache_query = cache_query.filter(Cache.stage == stage)

  for c in cache_query.filter(Cache.enabled.is_(True)).order_by(Cache.id).all():
    is_film = c.cache_kind == "film_loot"
    issued = (not is_film) or not stage2_on or c.id in issued_ids
    if stage2_player_view and stage2_on and is_film and c.id not in issued_ids:
      continue
    show_code = viewer_role in ("admin", "commander") or (stage2_player_view and issued)
    caches_out.append(
      CacheStatus(
        id=c.id,
        name=c.name,
        lat=c.lat,
        lon=c.lon,
        team_side=c.team_side,
        cache_kind=c.cache_kind or "post",
        destroyed=c.destroyed,
        destroyed_by_side=c.destroyed_by_side,
        delivered=c.delivered_at is not None,
        delivered_by_side=c.delivered_by_side,
        admin_confirmed=c.admin_confirmed,
        pending_admin=c.destroyed and not c.admin_confirmed,
        delivery_reported=c.delivery_reported_at is not None,
        pending_delivery_admin=c.delivery_reported_at is not None and c.delivered_at is None,
        enabled=c.enabled,
        stage2_issued=issued,
        stage2_active=stage2_on and is_film and c.id == active_stage2_id,
        loot_variant=c.loot_variant or "film_passage",
        code_verified=c.code_verified_at is not None if viewer_role == "admin" else False,
        detonation_code=c.detonation_code if show_code else None,
        entry_url=qr_entry_url(c.qr_token) if c.qr_token else None,
      )
    )

  landmarks_out = [
    LandmarkStatus(
      id=lm.id,
      name=lm.name,
      lat=lm.lat,
      lon=lm.lon,
      kind=lm.kind,
      team_side=lm.team_side,
      enabled=lm.enabled,
    )
    for lm in (
      db.query(Landmark)
      .filter(Landmark.scenario_id == scenario_id, Landmark.enabled.is_(True))
      .order_by(Landmark.id)
      .all()
    )
  ]

  hold_dm = settings.hold_deadman_seconds
  if map_point_stage == 1:
    hold_dm = point_hold_ping_seconds(game)
  elif stage == 3:
    hold_dm = post_hold_ping_seconds(game)

  return StatusResponse(
    game_status=game.status,
    current_stage=stage,
    stages=_stage_counts(db, scenario_id),
    score_a=score_a,
    score_b=score_b,
    points=points_out,
    caches=caches_out,
    landmarks=landmarks_out,
    capture_radius_m=capture_radius_m(game),
    disable_capture_distance=capture_distance_disabled(game),
    stage1_recapturable=stage1_recapturable(game),
    point_capture_seconds=point_capture_seconds(game),
    point_hold_ping_seconds=point_hold_ping_seconds(game),
    post_hold_seconds=post_hold_seconds(game),
    post_hold_ping_seconds=post_hold_ping_seconds(game),
    hold_deadman_seconds=hold_dm,
    stage2_issue_interval_minutes=game.stage2_issue_interval_minutes,
    stage2_issue_mode=game.stage2_issue_mode,
    stage2_next_issue_at=stage2_next_issue_at(game),
    stage2_enabled=bool(game.stage2_enabled),
    stage2_start_at=game.stage2_start_at,
    stage1_phase=stage1_phase,
    stage1_current_slot=current_slot_display,
    stage1_slot_count=slot_count,
    stage1_slot_ends_at=stage1_slot_ends_at(game) if show_stage1 else None,
    stage1_active_kt_numbers=active_kts,
    gps_accuracy_bonus_max_m=gps_accuracy_bonus_max_m(game),
    gps_min_accuracy_for_capture_m=gps_min_accuracy_for_capture_m(game),
    gps_lat_offset=gps_lat_offset(game),
    gps_lon_offset=gps_lon_offset(game),
    updated_at=datetime.utcnow(),
  )
