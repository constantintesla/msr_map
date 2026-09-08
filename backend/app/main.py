import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.migrate import run_migrations
from app.routers import admin, auth, cache, chat, commander, engineer, hold, location, map_grid, point, qr, scenarios, status, ws
from app.seed import seed_database
from app.services.cache_hold_service import close_expired_cache_holds
from app.services.hold_service import close_expired_holds
from app.services.stage2_assignment_service import maybe_auto_issue


async def stage2_issue_worker() -> None:
  """Фоновая автовыдача целей — только после ручного включения Задачи-2."""
  while True:
    db = SessionLocal()
    try:
      assignment = maybe_auto_issue(db)
      if assignment:
        await ws.broadcast_stage2_issued(assignment.cache_id)
    finally:
      db.close()
    await asyncio.sleep(60)


async def hold_expiry_worker() -> None:
  """Легковесная фоновая задача: только проверка expired holds (не баллы)."""
  while True:
    db = SessionLocal()
    try:
      closed = close_expired_holds(db)
      for session in closed:
        packet = {"e": "hold_expired", "p_id": session.point_id, "t": session.side}
        await ws.broadcast_hold_update(packet)
      cache_closed = close_expired_cache_holds(db)
      for session in cache_closed:
        await ws.broadcast_admin_event(
          {"e": "cache_hold_expired", "p_id": session.cache_id, "t": session.side}
        )
    finally:
      db.close()
    await asyncio.sleep(15)


@asynccontextmanager
async def lifespan(app: FastAPI):
  Base.metadata.create_all(bind=engine)
  run_migrations()
  seed_database()
  hold_task = asyncio.create_task(hold_expiry_worker())
  stage2_task = asyncio.create_task(stage2_issue_worker())
  yield
  hold_task.cancel()
  stage2_task.cancel()
  try:
    await hold_task
    await stage2_task
  except asyncio.CancelledError:
    pass


app = FastAPI(title="MSR Map API", lifespan=lifespan)

app.add_middleware(
  CORSMiddleware,
  allow_origins=settings.cors_origins_list,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(status.router)
app.include_router(chat.router)
app.include_router(location.router)
app.include_router(commander.router)
app.include_router(engineer.router)
app.include_router(hold.router)
app.include_router(cache.router)
app.include_router(point.router)
app.include_router(admin.router)
app.include_router(scenarios.router)
app.include_router(map_grid.router)
app.include_router(qr.router)
app.include_router(ws.router)


@app.get("/health")
def health():
  return {"status": "ok"}
