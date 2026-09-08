from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
  username: str
  password: str


class TokenResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"
  user_id: int
  role: str
  side: str | None = None
  point_id: int | None = None
  cache_id: int | None = None
  lpd_channel: int | None = None
  lpd_frequency_mhz: float | None = None
  lpd_label: str | None = None


class GameSettingsOut(BaseModel):
  engineers_per_side_a: int
  engineers_per_side_b: int
  engineers_count_a: int = 0
  engineers_count_b: int = 0
  capture_radius_m: int = 10
  disable_capture_distance: bool = False
  stage1_recapturable: bool = True
  point_capture_seconds: int = 120
  point_hold_ping_seconds: int = 120
  post_hold_seconds: int = 600
  post_hold_ping_seconds: int = 120
  stage2_issue_interval_minutes: int = 60
  stage2_issue_mode: str = "random"
  stage2_enabled: bool = False
  stage2_start_at: datetime | None = None
  stage1_slot_minutes: int = 120
  stage1_hold_slots: list[list[int]] = Field(
    default_factory=lambda: [[2, 3, 6, 8, 10], [4, 5, 9, 11, 12], [1, 3, 6, 7, 10]]
  )
  gps_accuracy_bonus_max_m: int = 20
  gps_min_accuracy_for_capture_m: int = 0
  gps_lat_offset: float = 0.0
  gps_lon_offset: float = 0.0


class GameSettingsUpdate(BaseModel):
  engineers_per_side_a: int = Field(ge=1, le=50)
  engineers_per_side_b: int = Field(ge=1, le=50)
  capture_radius_m: int = Field(ge=1, le=500, default=10)
  disable_capture_distance: bool = False
  stage1_recapturable: bool = True
  point_capture_seconds: int = Field(ge=30, le=3600, default=120)
  point_hold_ping_seconds: int = Field(ge=15, le=3600, default=120)
  post_hold_seconds: int = Field(ge=60, le=7200, default=600)
  post_hold_ping_seconds: int = Field(ge=15, le=3600, default=120)
  stage2_issue_interval_minutes: int = Field(ge=1, le=1440, default=60)
  stage2_issue_mode: str = Field(default="random", pattern="^(random|sequential)$")
  stage2_enabled: bool = False
  stage2_start_at: datetime | None = None
  stage1_slot_minutes: int = Field(ge=1, le=1440, default=120)
  stage1_hold_slots: list[list[int]] | None = None
  gps_accuracy_bonus_max_m: int = Field(ge=0, le=100, default=20)
  gps_min_accuracy_for_capture_m: int = Field(ge=0, le=200, default=0)
  gps_lat_offset: float = Field(default=0.0, ge=-1.0, le=1.0)
  gps_lon_offset: float = Field(default=0.0, ge=-1.0, le=1.0)


class GpsCalibrateRequest(BaseModel):
  true_lat: float
  true_lon: float
  measured_lat: float
  measured_lon: float


class LpdChannelOut(BaseModel):
  channel: int
  frequency_mhz: float


class EngineerPoolItem(BaseModel):
  id: int
  username: str
  side: str
  password_hint: str
  lpd_channel: int | None = None
  lpd_frequency_mhz: float | None = None
  lpd_label: str | None = None


class EngineerChannelUpdate(BaseModel):
  lpd_channel: int | None = Field(default=None, ge=1, le=69)


class EngineerProfileOut(BaseModel):
  username: str
  side: str
  lpd_channel: int | None = None
  lpd_frequency_mhz: float | None = None
  lpd_label: str | None = None
  point_id: int | None = None
  cache_id: int | None = None


class FieldOrderCreate(BaseModel):
  engineer_user_id: int
  target_kind: str = Field(pattern="^(point|cache)$")
  target_id: int
  note: str | None = Field(default=None, max_length=500)


class FieldOrderOut(BaseModel):
  id: int
  created_at: datetime
  side: str
  commander_username: str
  engineer_username: str
  target_kind: str
  target_id: int
  target_name: str
  target_lat: float
  target_lon: float
  note: str | None = None
  acknowledged_at: datetime | None = None
  dismissed: bool = False


class FieldOrderDismissResponse(BaseModel):
  ok: bool = True
  order: FieldOrderOut | None = None


class PointStatus(BaseModel):
  id: int
  name: str
  lat: float
  lon: float
  side: str | None
  held_by: str | None = None
  held_by_user_id: int | None = None
  hold_started_at: datetime | None = None
  last_ping_at: datetime | None = None
  hold_ready: bool = False
  hold_elapsed_sec: int = 0
  destroyed: bool = False
  destroyed_by_side: str | None = None
  admin_confirmed: bool = False
  pending_admin: bool = False
  kt_number: int | None = None
  stage1_capturable: bool = False
  entry_url: str | None = None
  enabled: bool = True


class CacheStatus(BaseModel):
  id: int
  name: str
  lat: float
  lon: float
  team_side: str | None = None
  cache_kind: str = "post"
  destroyed: bool
  destroyed_by_side: str | None = None
  delivered: bool = False
  delivered_by_side: str | None = None
  held_by: str | None = None
  hold_started_at: datetime | None = None
  hold_ready: bool = False
  hold_elapsed_sec: int = 0
  admin_confirmed: bool = False
  pending_admin: bool = False
  delivery_reported: bool = False
  pending_delivery_admin: bool = False
  enabled: bool = True
  stage2_issued: bool = True
  stage2_active: bool = False
  loot_variant: str = "film_passage"
  code_verified: bool = False
  detonation_code: str | None = None
  entry_url: str | None = None


class DeliverRequest(BaseModel):
  cache_id: int
  side: str = Field(pattern="^[AB]$")
  lat: float
  lon: float


class LandmarkStatus(BaseModel):
  id: int
  name: str
  lat: float
  lon: float
  kind: str  # base | start | base_start
  team_side: str
  enabled: bool = True


class StageInfo(BaseModel):
  stage: int
  label: str
  points_count: int
  caches_count: int


class MapGridOut(BaseModel):
  north: float
  south: float
  east: float
  west: float
  image_url: str


class SideScoreBreakdown(BaseModel):
  hold: int = 0
  captures: int = 0
  loot_breach: int = 0
  loot_deliver: int = 0
  posts: int = 0
  caches: int = 0


class ScoreBreakdownResponse(BaseModel):
  score_a: int
  score_b: int
  breakdown_a: SideScoreBreakdown
  breakdown_b: SideScoreBreakdown


class StatusResponse(BaseModel):
  game_status: str
  current_stage: int = 1
  stages: list[StageInfo] = []
  score_a: int | None = None
  score_b: int | None = None
  points: list[PointStatus]
  caches: list[CacheStatus]
  landmarks: list[LandmarkStatus] = []
  capture_radius_m: int = 10
  disable_capture_distance: bool = False
  stage1_recapturable: bool = True
  point_capture_seconds: int = 120
  point_hold_ping_seconds: int = 120
  post_hold_seconds: int = 600
  post_hold_ping_seconds: int = 120
  hold_deadman_seconds: int = 120
  stage2_issue_interval_minutes: int = 60
  stage2_issue_mode: str = "random"
  stage2_next_issue_at: datetime | None = None
  stage2_enabled: bool = False
  stage2_start_at: datetime | None = None
  stage1_phase: str | None = None
  stage1_current_slot: int | None = None
  stage1_slot_count: int = 0
  stage1_slot_ends_at: datetime | None = None
  stage1_active_kt_numbers: list[int] = []
  gps_accuracy_bonus_max_m: int = 20
  gps_min_accuracy_for_capture_m: int = 0
  gps_lat_offset: float = 0.0
  gps_lon_offset: float = 0.0
  updated_at: datetime


class Stage2ActiveLootOut(BaseModel):
  cache_id: int
  name: str
  lat: float
  lon: float
  code: str
  loot_variant: str
  url: str


class CommanderStatusResponse(StatusResponse):
  viewer_side: str
  side_label: str
  stage2_active_loot: Stage2ActiveLootOut | None = None


class FeedItem(BaseModel):
  id: int
  created_at: str
  event_type: str
  text: str
  is_broadcast: bool = False


class CommanderFeedResponse(BaseModel):
  items: list[FeedItem]


class BroadcastRequest(BaseModel):
  message: str = Field(min_length=1, max_length=500)
  target_side: str = Field(pattern="^(A|B|ALL)$")


class ChatMessageOut(BaseModel):
  id: int
  created_at: datetime
  side: str
  thread: str = "cmd"
  sender_role: str
  sender_name: str
  text: str | None = None
  media_type: str | None = None
  has_media: bool = False
  media_filename: str | None = None
  recipient_username: str | None = None


class ChatRecipientOut(BaseModel):
  username: str


class ChatMessagesResponse(BaseModel):
  side: str
  thread: str = "cmd"
  items: list[ChatMessageOut]


class LocationPingRequest(BaseModel):
  lat: float
  lon: float
  accuracy: float = 0.0


class EngineerLocationOut(BaseModel):
  user_id: int
  username: str
  side: str
  label: str
  lat: float
  lon: float
  accuracy: float
  updated_at: datetime


class MovementTrackPointOut(BaseModel):
  lat: float
  lon: float
  accuracy: float
  recorded_at: datetime


class MovementTrackUserOut(BaseModel):
  user_id: int
  username: str
  side: str
  label: str
  points: list[MovementTrackPointOut]


class MovementTracksResponse(BaseModel):
  game_session_id: int
  game_status: str
  game_started_at: datetime | None
  tracks: list[MovementTrackUserOut]
  total_points: int


class HoldConfirmRequest(BaseModel):
  point_id: int
  side: str = Field(pattern="^[AB]$")


class HoldLeaveRequest(BaseModel):
  point_id: int
  side: str = Field(pattern="^[AB]$")


class CacheHoldConfirmRequest(BaseModel):
  cache_id: int
  side: str = Field(pattern="^[AB]$")
  lat: float | None = None
  lon: float | None = None
  accuracy: float | None = None


class CacheHoldLeaveRequest(BaseModel):
  cache_id: int
  side: str = Field(pattern="^[AB]$")


class PointBeginCaptureRequest(BaseModel):
  point_id: int
  side: str = Field(pattern="^[AB]$")
  code: str = Field(pattern=r"^\d{4,6}$")
  lat: float
  lon: float
  accuracy: float | None = None


class PointDetonateRequest(BaseModel):
  point_id: int
  code: str = Field(min_length=4, max_length=6)
  side: str = Field(pattern="^[AB]$")


class DetonateRequest(BaseModel):
  cache_id: int
  code: str = Field(min_length=4, max_length=6)
  side: str = Field(pattern="^[AB]$")


class CacheCodeRequest(BaseModel):
  cache_id: int
  code: str = Field(min_length=4, max_length=6)
  side: str = Field(pattern="^[AB]$")
  qr_token: str = Field(min_length=8, max_length=24)
  lat: float | None = None
  lon: float | None = None
  accuracy: float | None = None


class AdminActionResponse(BaseModel):
  ok: bool
  message: str


class ScenarioOut(BaseModel):
  id: int
  name: str
  slug: str
  is_active: bool
  created_at: datetime


class ScenarioCreate(BaseModel):
  name: str = Field(min_length=1, max_length=128)


class BulkMapEnabledRequest(BaseModel):
  enabled: bool
  points: bool = True
  caches: bool = True
  landmarks: bool = True


class AdminCacheConfirmBody(BaseModel):
  """Подтверждение схрона/лутa админом. side обязателен для вскрытия без видео в системе."""
  side: str | None = Field(default=None, pattern="^[AB]$")


class Stage1CodeUpdate(BaseModel):
  code: str = Field(pattern=r"^\d{4,6}$")


class Stage2MissionUpdate(BaseModel):
  code: str | None = Field(default=None, pattern=r"^\d{4,6}$")
  enabled: bool | None = None


class MertvyakUpdate(BaseModel):
  enabled: bool | None = None
  code: str | None = Field(default=None, pattern=r"^\d{4,6}$")


class Stage2MissionItem(BaseModel):
  id: int
  name: str
  lat: float
  lon: float
  code: str
  url: str
  enabled: bool = True


class Stage2AssignmentItem(BaseModel):
  id: int
  cache_id: int
  cache_name: str
  assigned_at: datetime
  round_number: int
  destroyed: bool = False
  destroyed_by_side: str | None = None
  delivered: bool = False
  delivered_by_side: str | None = None


class MapPointCreate(BaseModel):
  lat: float
  lon: float
  stage: int = Field(ge=1, le=3)
  name: str | None = Field(default=None, max_length=128)


class MapPointUpdate(BaseModel):
  lat: float | None = None
  lon: float | None = None
  name: str | None = Field(default=None, max_length=128)


class MapCacheCreate(BaseModel):
  lat: float
  lon: float
  stage: int = Field(ge=2, le=3)
  cache_kind: str = Field(pattern=r"^(film_loot|post|mertvyak)$")
  team_side: str | None = Field(default=None, pattern=r"^[AB]$")
  name: str | None = Field(default=None, max_length=128)
  loot_variant: str | None = Field(default="film_passage", pattern=r"^(film_passage|box_direct)$")


class MapCacheUpdate(BaseModel):
  lat: float | None = None
  lon: float | None = None
  name: str | None = Field(default=None, max_length=128)
  team_side: str | None = Field(default=None, pattern=r"^[AB]$")


class MapLandmarkCreate(BaseModel):
  lat: float
  lon: float
  kind: str = Field(pattern=r"^(base|start|base_start)$")
  team_side: str = Field(pattern=r"^[AB]$")
  name: str | None = Field(default=None, max_length=128)


class MapLandmarkUpdate(BaseModel):
  lat: float | None = None
  lon: float | None = None
  name: str | None = Field(default=None, max_length=128)
  kind: str | None = Field(default=None, pattern=r"^(base|start|base_start)$")
  team_side: str | None = Field(default=None, pattern=r"^[AB]$")


class MapObjectOut(BaseModel):
  id: int
  name: str
  lat: float
  lon: float
  kind: str | None = None
  stage: int | None = None
  cache_kind: str | None = None
  team_side: str | None = None


class WsPacket(BaseModel):
  e: str
  p_id: int | None = None
  t: str | None = None
  data: dict[str, Any] | None = None
