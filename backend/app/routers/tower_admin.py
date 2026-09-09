import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.config import settings
from app.database import get_db
from app.models import Scenario, User
from app.qr_tokens import qr_entry_url
from app.tower import commander_service
from app.tower.config_service import get_phases, get_tower_config, set_phases
from app.tower.media import elder_photo_url, save_elder_photo
from app.tower.models import Faction, UrPoint, UrZone
from app.tower.schemas import (
  TowerAdminOverviewOut,
  TowerAdminRosterItemOut,
  TowerCommanderAdminOut,
  TowerFactionAdminOut,
  TowerFactionAdminUpdate,
  TowerPhaseSetRequest,
  TowerPhasesUpdate,
  TowerRevealScheduleUpdate,
  TowerUrPointAdminOut,
  TowerUrZoneAdminOut,
)
from app.tower.seed import seed_tower_scenario
from app.tower.ur_service import refresh_all_zones

router = APIRouter(prefix="/api/admin/tower", tags=["tower-admin"])


def _join_url(token: str) -> str:
  base = settings.public_app_url.rstrip("/")
  return f"{base}/#/join/{token}"


@router.post("/seed", response_model=TowerAdminOverviewOut)
def seed(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  scenario = seed_tower_scenario(db)
  return _overview(db, scenario.id)


def _overview(db: Session, scenario_id: int) -> TowerAdminOverviewOut:
  factions = db.query(Faction).filter(Faction.scenario_id == scenario_id).order_by(Faction.id).all()
  faction_out = []
  commanders_out = []
  for f in factions:
    registered = db.query(User).filter(User.faction_id == f.id, User.role == "faction").count()
    faction_out.append(
      TowerFactionAdminOut(
        id=f.id,
        code=f.code,
        name=f.name,
        kind=f.kind,
        elder_note=f.elder_note,
        elder_photo_url=elder_photo_url(f.elder_photo_path),
        drop_lat=f.drop_lat,
        drop_lon=f.drop_lon,
        join_url=_join_url(f.join_token) if f.join_token else None,
        qr_url=qr_entry_url(f.qr_token) if f.qr_token else None,
        registered_count=registered,
      )
    )
    cmd = (
      db.query(User)
      .filter(User.faction_id == f.id, User.role == "commander")
      .order_by(User.id)
      .first()
    )
    if cmd is not None:
      commanders_out.append(
        TowerCommanderAdminOut(
          faction_code=f.code,
          faction_name=f.name,
          username=cmd.username,
          password=cmd.password_plain or "—",
        )
      )

  zones = refresh_all_zones(db, scenario_id)
  cfg = get_tower_config(db, scenario_id)
  zones_out = []
  for zone in zones:
    points = db.query(UrPoint).filter(UrPoint.zone_id == zone.id).order_by(UrPoint.id).all()
    hold_ends_at = None
    if zone.status == "holding" and zone.hold_started_at:
      from datetime import timedelta

      hold_ends_at = zone.hold_started_at + timedelta(seconds=cfg.ur_hold_seconds)
    zones_out.append(
      TowerUrZoneAdminOut(
        id=zone.id,
        name=zone.name,
        status=zone.status,
        hold_ends_at=hold_ends_at,
        points=[
          TowerUrPointAdminOut(
            id=p.id,
            name=p.name,
            scanned=p.last_sbg_scan_at is not None,
            qr_url=qr_entry_url(p.qr_token) if p.qr_token else None,
          )
          for p in points
        ],
      )
    )

  schedule = sorted(json.loads(cfg.reveal_schedule_json)) if cfg.reveal_schedule_json else []
  return TowerAdminOverviewOut(
    scenario_id=scenario_id,
    factions=faction_out,
    commanders=commanders_out,
    ur_zones=zones_out,
    reveal_schedule=[datetime.fromisoformat(t) for t in schedule],
    ur_sync_window_seconds=cfg.ur_sync_window_seconds,
    ur_hold_seconds=cfg.ur_hold_seconds,
    phases=get_phases(cfg),
    current_phase=cfg.current_phase,
  )


def _tower_scenario_id(db: Session) -> int:
  scenario = db.query(Scenario).filter(Scenario.name == "Башня", Scenario.archived_at.is_(None)).first()
  if scenario is None:
    raise HTTPException(status_code=404, detail="Сценарий «Башня» ещё не создан")
  return scenario.id


@router.get("/overview", response_model=TowerAdminOverviewOut)
def overview(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  return _overview(db, _tower_scenario_id(db))


@router.patch("/factions/{faction_id}", response_model=TowerFactionAdminOut)
def update_faction(
  faction_id: int,
  body: TowerFactionAdminUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  faction = db.query(Faction).filter(Faction.id == faction_id).first()
  if faction is None:
    raise HTTPException(status_code=404, detail="Сторона не найдена")
  if body.elder_note is not None:
    faction.elder_note = body.elder_note
  if body.drop_lat is not None:
    faction.drop_lat = body.drop_lat
  if body.drop_lon is not None:
    faction.drop_lon = body.drop_lon
  db.commit()
  overview_out = _overview(db, faction.scenario_id)
  match = next(f for f in overview_out.factions if f.id == faction_id)
  return match


@router.post("/ur-zones/{zone_id}/reset")
def reset_zone(
  zone_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  zone = db.query(UrZone).filter(UrZone.id == zone_id).first()
  if zone is None:
    raise HTTPException(status_code=404, detail="УР не найден")
  for p in db.query(UrPoint).filter(UrPoint.zone_id == zone.id).all():
    p.last_sbg_scan_at = None
  zone.status = "idle"
  zone.sync_started_at = None
  zone.hold_started_at = None
  zone.captured_at = None
  db.commit()
  return {"ok": True}


@router.patch("/reveal-schedule")
def update_reveal_schedule(
  body: TowerRevealScheduleUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  scenario_id = _tower_scenario_id(db)
  cfg = get_tower_config(db, scenario_id)
  cfg.reveal_schedule_json = json.dumps([t.isoformat() for t in body.thresholds])
  db.commit()
  return {"ok": True}


@router.post("/factions/{faction_id}/elder-photo", response_model=TowerFactionAdminOut)
async def upload_elder_photo(
  faction_id: int,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
  file: Annotated[UploadFile, File(...)],
):
  faction = db.query(Faction).filter(Faction.id == faction_id).first()
  if faction is None:
    raise HTTPException(status_code=404, detail="Сторона не найдена")
  filename = await save_elder_photo(file)
  faction.elder_photo_path = filename
  db.commit()
  overview_out = _overview(db, faction.scenario_id)
  return next(f for f in overview_out.factions if f.id == faction_id)


@router.patch("/phases")
def update_phases(
  body: TowerPhasesUpdate,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  scenario_id = _tower_scenario_id(db)
  cfg = get_tower_config(db, scenario_id)
  set_phases(cfg, body.phases)
  db.commit()
  return {"ok": True, "phases": get_phases(cfg)}


@router.post("/phases/current")
def set_current_phase(
  body: TowerPhaseSetRequest,
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  scenario_id = _tower_scenario_id(db)
  cfg = get_tower_config(db, scenario_id)
  phases = get_phases(cfg)
  if body.phase >= len(phases):
    raise HTTPException(status_code=400, detail="Такого этапа нет в списке")
  cfg.current_phase = body.phase
  db.commit()
  return {"ok": True, "current_phase": cfg.current_phase, "phase_name": phases[body.phase]}


@router.get("/roster", response_model=list[TowerAdminRosterItemOut])
def roster(
  db: Annotated[Session, Depends(get_db)],
  _: Annotated[User, Depends(require_admin)],
):
  """Живые позиции всех сторон разом — для карты в админке."""
  scenario_id = _tower_scenario_id(db)
  rows = commander_service.list_roster_for_scenario(db, scenario_id)
  factions = {f.id: f for f in db.query(Faction).filter(Faction.scenario_id == scenario_id).all()}
  out = []
  for r in rows:
    faction = factions.get(r.faction_id)
    out.append(
      TowerAdminRosterItemOut(
        user_id=r.user_id,
        username=r.username,
        faction_id=r.faction_id,
        lat=r.lat,
        lon=r.lon,
        accuracy=r.accuracy,
        updated_at=r.updated_at,
        faction_code=faction.code if faction else "?",
        faction_name=faction.name if faction else "?",
      )
    )
  return out
