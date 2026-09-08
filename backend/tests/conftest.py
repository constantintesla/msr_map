"""Общие фикстуры для тестов MSR Map."""

from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password
from app.config import settings
from app.database import Base, get_db
from app.routers import admin, auth, cache, hold, location, point, scenarios
from app.models import Cache, GameState, GameStatus, Landmark, Point, User
from app.services.game_service import start_game


@pytest.fixture
def db_engine():
  engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  Base.metadata.create_all(bind=engine)
  yield engine
  engine.dispose()


@pytest.fixture
def db(db_engine) -> Generator[Session, None, None]:
  session = sessionmaker(bind=db_engine)()
  yield session
  session.close()


def make_point(
  db: Session,
  *,
  point_id: int = 1,
  stage: int = 1,
  side: str | None = None,
  lat: float = 44.529392,
  lon: float = 132.828296,
  name: str = "КТ1",
  detonation_code: str | None = None,
) -> Point:
  point = Point(
    id=point_id,
    name=name,
    lat=lat,
    lon=lon,
    stage=stage,
    side=side,
    detonation_code=detonation_code,
  )
  db.add(point)
  db.commit()
  db.refresh(point)
  return point


def make_user(
  db: Session,
  *,
  user_id: int = 1,
  username: str = "eng_a1",
  side: str = "A",
  role: str = "engineer",
) -> User:
  user = User(
    id=user_id,
    username=username,
    password_hash=hash_password("test"),
    role=role,
    side=side,
  )
  db.add(user)
  db.commit()
  db.refresh(user)
  return user


def make_running_game(
  db: Session,
  *,
  stage: int = 1,
  stage2_enabled: bool = False,
  capture_radius_m: int = 10,
  disable_capture_distance: bool = False,
  stage1_recapturable: bool = True,
  point_capture_seconds: int = 120,
  point_hold_ping_seconds: int = 120,
  post_hold_seconds: int = 600,
  post_hold_ping_seconds: int = 120,
  started_minutes_ago: int = 0,
  stage1_slots_started: bool = False,
  stage1_slots_started_minutes_ago: int = 0,
) -> GameState:
  state = GameState(
    id=1,
    status=GameStatus.IDLE.value,
    current_stage=stage,
    stage2_enabled=stage2_enabled or stage == 2,
    capture_radius_m=capture_radius_m,
    disable_capture_distance=disable_capture_distance,
    stage1_recapturable=stage1_recapturable,
    point_capture_seconds=point_capture_seconds,
    point_hold_ping_seconds=point_hold_ping_seconds,
    post_hold_seconds=post_hold_seconds,
    post_hold_ping_seconds=post_hold_ping_seconds,
  )
  db.add(state)
  db.commit()
  start_game(db)
  state = db.query(GameState).filter(GameState.id == 1).first()
  state.current_stage = stage
  if stage1_slots_started:
    ago = stage1_slots_started_minutes_ago
    state.stage1_slots_started_at = datetime.utcnow() - timedelta(minutes=ago)
    state.stage1_current_slot = 0
  if started_minutes_ago > 0:
    state.started_at = datetime.utcnow() - timedelta(minutes=started_minutes_ago)
  db.commit()
  db.refresh(state)
  return state


def make_cache(
  db: Session,
  *,
  cache_id: int = 1,
  stage: int = 2,
  cache_kind: str = "film_loot",
  detonation_code: str = "1001",
  team_side: str | None = None,
  lat: float = 44.529392,
  lon: float = 132.828296,
  name: str = "Ящик-1",
  loot_variant: str = "film_passage",
  enabled: bool = True,
) -> Cache:
  from app.qr_tokens import ensure_cache_qr_token

  cache_obj = Cache(
    id=cache_id,
    name=name,
    lat=lat,
    lon=lon,
    stage=stage,
    cache_kind=cache_kind,
    detonation_code=detonation_code,
    team_side=team_side,
    loot_variant=loot_variant,
    enabled=enabled,
  )
  db.add(cache_obj)
  db.commit()
  ensure_cache_qr_token(cache_obj, db)
  db.commit()
  db.refresh(cache_obj)
  return cache_obj


def make_landmark(
  db: Session,
  *,
  landmark_id: int = 1,
  name: str = "База ЛК",
  lat: float = 44.530000,
  lon: float = 132.829000,
  kind: str = "base",
  team_side: str = "A",
) -> Landmark:
  landmark = Landmark(id=landmark_id, name=name, lat=lat, lon=lon, kind=kind, team_side=team_side)
  db.add(landmark)
  db.commit()
  db.refresh(landmark)
  return landmark


def auth_header(user: User) -> dict[str, str]:
  token = create_access_token({"sub": user.username})
  return {"Authorization": f"Bearer {token}"}


def create_test_app() -> FastAPI:
  test_app = FastAPI()
  test_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  test_app.include_router(auth.router)
  test_app.include_router(admin.router)
  test_app.include_router(scenarios.router)
  test_app.include_router(hold.router)
  test_app.include_router(point.router)
  test_app.include_router(cache.router)
  test_app.include_router(location.router)
  return test_app


@pytest.fixture
def client(db_engine) -> Generator[TestClient, None, None]:
  SessionLocal = sessionmaker(bind=db_engine)

  def override_get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
      yield session
    finally:
      session.close()

  test_app = create_test_app()
  test_app.dependency_overrides[get_db] = override_get_db
  with TestClient(test_app) as test_client:
    yield test_client
  test_app.dependency_overrides.clear()
