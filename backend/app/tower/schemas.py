from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- сканирование ---


class TowerScanRequest(BaseModel):
  token: str | None = Field(default=None, max_length=32)
  code: str | None = Field(default=None, max_length=6)


class TowerScanResponse(BaseModel):
  kind: str  # village | ur_zone
  data: dict[str, Any]


# --- регистрация по ссылке стороны ---


class TowerJoinInfoOut(BaseModel):
  faction_code: str
  faction_name: str


class TowerRegisterRequest(BaseModel):
  callsign: str = Field(min_length=2, max_length=24)
  pin: str = Field(pattern=r"^\d{4}$")


# --- админка Башни ---


class TowerFactionAdminOut(BaseModel):
  id: int
  code: str
  name: str
  kind: str
  elder_note: str | None = None
  elder_photo_url: str | None = None
  join_url: str | None = None
  qr_url: str | None = None
  manual_code: str | None = None
  registered_count: int = 0
  cache_revealed_count: int = 0
  cache_total: int = 0


class TowerFactionAdminUpdate(BaseModel):
  elder_note: str | None = None


class TowerCommanderAdminOut(BaseModel):
  faction_code: str
  faction_name: str
  username: str
  password: str


class TowerUrPointAdminOut(BaseModel):
  id: int
  name: str
  scanned: bool
  qr_url: str | None = None
  manual_code: str | None = None


class TowerUrZoneAdminOut(BaseModel):
  id: int
  name: str
  status: str
  hold_ends_at: datetime | None = None
  points: list[TowerUrPointAdminOut] = []


class TowerRevealScheduleUpdate(BaseModel):
  thresholds: list[datetime] = Field(default_factory=list)


class TowerAdminOverviewOut(BaseModel):
  scenario_id: int
  factions: list[TowerFactionAdminOut]
  commanders: list[TowerCommanderAdminOut]
  ur_zones: list[TowerUrZoneAdminOut]
  reveal_schedule: list[datetime] = []
  ur_sync_window_seconds: int
  ur_hold_seconds: int


# --- чат / приказы / геолокация (faction-scoped аналог side-based) ---


class TowerChatMessageOut(BaseModel):
  id: int
  created_at: datetime
  faction_id: int
  thread: str = "cmd"
  sender_role: str
  sender_name: str
  text: str | None = None
  media_type: str | None = None
  has_media: bool = False
  media_filename: str | None = None
  recipient_username: str | None = None


class TowerChatMessagesResponse(BaseModel):
  faction_id: int
  thread: str = "cmd"
  items: list[TowerChatMessageOut]


class TowerChatRecipientOut(BaseModel):
  username: str


class TowerOrderCreate(BaseModel):
  target_username: str = Field(min_length=2, max_length=24)
  target_name: str = Field(min_length=1, max_length=128)
  target_lat: float
  target_lon: float
  note: str | None = Field(default=None, max_length=500)


class TowerOrderOut(BaseModel):
  id: int
  created_at: datetime
  faction_id: int
  commander_username: str
  target_username: str
  target_name: str
  target_lat: float
  target_lon: float
  note: str | None = None
  dismissed: bool = False


class TowerOrderDismissResponse(BaseModel):
  ok: bool = True
  order: TowerOrderOut | None = None


class TowerLocationPingRequest(BaseModel):
  lat: float
  lon: float
  accuracy: float = 0.0


class TowerLocationOut(BaseModel):
  user_id: int
  username: str
  faction_id: int
  lat: float
  lon: float
  accuracy: float
  updated_at: datetime


class TowerAdminRosterItemOut(TowerLocationOut):
  faction_code: str
  faction_name: str
