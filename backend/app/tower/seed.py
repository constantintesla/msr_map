"""Разовое создание сценария «Башня» со сторонами, деревенскими схронами,
укрепрайонами и справочными точками карты. Вызывается вручную из админки
(кнопка), НЕ при каждом старте приложения — в отличие от app/seed.py."""

import random

from sqlalchemy.orm import Session

from app.models import GameState, Landmark, Scenario
from app.qr_tokens import generate_qr_token
from app.services.engineer_pool_service import generate_engineer_password
from app.services.scenario_service import create_scenario
from app.tower.config_service import get_tower_config
from app.tower.models import Faction, TowerConfig, UrPoint, UrZone, VillageCacheTarget

TOWER_SCENARIO_NAME = "Башня"

# lat, lon — из Башня.kml (координаты в KML идут как lon,lat — тут уже переставлено)
VILLAGES = {
  "prvonek": {"name": "Првонек", "lat": 44.226893, "lon": 131.695014},
  "korbul": {"name": "Корбул", "lat": 44.224225, "lon": 131.699268},
}

VILLAGE_CACHES = {
  "prvonek": [
    ("Д1-1", 44.227327, 131.693727),
    ("Д1-2", 44.228319, 131.694381),
    ("Д1-3", 44.229026, 131.697321),
  ],
  "korbul": [
    ("Д2-1", 44.225121, 131.699606),
    ("Д2-2", 44.224728, 131.701591),
    ("Д2-3", 44.223521, 131.702814),
  ],
}

UR_ZONES = {
  "УР1": [
    ("КПП1-1", 44.226189, 131.692472),
    ("КПП1-2", 44.226589, 131.693909),
    ("КПП1-3", 44.225666, 131.694328),
  ],
  "УР2": [
    ("КПП2-1", 44.225293, 131.696216),
    ("КПП2-2", 44.226143, 131.697133),
    ("КПП2-3", 44.225290, 131.698346),
  ],
  "УР3": [
    ("КПП3-1", 44.224098, 131.696640),
    ("КПП3-2", 44.224755, 131.697637),
    ("КПП3-3", 44.224129, 131.698249),
  ],
  "УР4": [
    ("КПП4-1", 44.222841, 131.698903),
    ("КПП4-2", 44.221676, 131.699461),
    ("КПП4-3", 44.221230, 131.698367),
  ],
}

# Справочные точки — импортируются как обычные Landmark(kind="reference"),
# без игровой логики, просто чтобы мастер видел их на карте в админке.
REFERENCE_LANDMARKS = [
  ("О1", 44.221972, 131.700395), ("О2", 44.222368, 131.699322), ("О3", 44.222729, 131.698378),
  ("О4", 44.223122, 131.697391), ("О5", 44.223460, 131.696463), ("О6", 44.223960, 131.695250),
  ("О7", 44.224332, 131.694247), ("О8", 44.224717, 131.693212), ("О9", 44.225059, 131.692305),
  ("О10", 44.225470, 131.691313), ("О11", 44.225847, 131.690267), ("О12", 44.226243, 131.689274),
  ("Лагерь СБГ", 44.229672, 131.690154), ("Парковка", 44.228373, 131.685959),
  ("Шахта 1", 44.225643, 131.695620), ("Шахта 2", 44.224725, 131.696447), ("Шахта 3", 44.223756, 131.697283),
  ("М1", 44.228111, 131.695915), ("М2", 44.223936, 131.701076),
  ("Г1", 44.227431, 131.690288), ("Г2", 44.222699, 131.695197), ("Г3", 44.219500, 131.700228),
]


def _generate_manual_code(existing: set[str]) -> str:
  for _ in range(50):
    code = f"{random.randint(1000, 9999)}"
    if code not in existing:
      existing.add(code)
      return code
  raise RuntimeError("Не удалось сгенерировать уникальный код")


def seed_tower_scenario(db: Session) -> Scenario:
  scenario = db.query(Scenario).filter(Scenario.name == TOWER_SCENARIO_NAME, Scenario.archived_at.is_(None)).first()
  if scenario is not None:
    already_seeded = db.query(Faction).filter(Faction.scenario_id == scenario.id).first() is not None
    if already_seeded:
      return scenario
    # Сценарий существует, но не досеялся до конца (например, оборвалось на
    # середине из-за инфраструктурной ошибки) — не оставляем пустую заглушку
    # навсегда, а сносим её и сеем заново с чистого листа.
    db.query(GameState).filter(GameState.id == scenario.id).delete()
    db.query(TowerConfig).filter(TowerConfig.id == scenario.id).delete()
    db.query(Scenario).filter(Scenario.id == scenario.id).delete()
    db.commit()

  scenario = create_scenario(db, TOWER_SCENARIO_NAME)
  db.add(GameState(id=scenario.id, engineers_per_side_a=0, engineers_per_side_b=0))
  get_tower_config(db, scenario.id)
  db.flush()

  used_codes: set[str] = set()

  factions: dict[str, Faction] = {}
  for code, name, kind in (
    ("sbg", "СБГ", "ops"),
    ("drg", "ДРГ", "ops"),
    ("prvonek", VILLAGES["prvonek"]["name"], "village"),
    ("korbul", VILLAGES["korbul"]["name"], "village"),
  ):
    faction = Faction(
      scenario_id=scenario.id,
      code=code,
      name=name,
      kind=kind,
      join_token=generate_qr_token(),
      manual_code=_generate_manual_code(used_codes),
    )
    if code in VILLAGES:
      faction.lat = VILLAGES[code]["lat"]
      faction.lon = VILLAGES[code]["lon"]
      faction.qr_token = generate_qr_token()
    db.add(faction)
    db.flush()
    factions[code] = faction

  for village_code, targets in VILLAGE_CACHES.items():
    order = list(range(1, len(targets) + 1))
    random.shuffle(order)
    for (name, lat, lon), reveal_order in zip(targets, order, strict=True):
      db.add(
        VillageCacheTarget(
          scenario_id=scenario.id,
          faction_id=factions[village_code].id,
          name=name,
          lat=lat,
          lon=lon,
          reveal_order=reveal_order,
        )
      )

  for zone_index, (zone_name, points) in enumerate(UR_ZONES.items()):
    zone = UrZone(scenario_id=scenario.id, name=zone_name, order=zone_index, status="idle")
    db.add(zone)
    db.flush()
    for name, lat, lon in points:
      db.add(
        UrPoint(
          scenario_id=scenario.id,
          zone_id=zone.id,
          name=name,
          lat=lat,
          lon=lon,
          qr_token=generate_qr_token(),
          manual_code=_generate_manual_code(used_codes),
        )
      )

  for name, lat, lon in REFERENCE_LANDMARKS:
    db.add(
      Landmark(scenario_id=scenario.id, name=name, lat=lat, lon=lon, kind="reference", team_side="A")
    )

  for code, cmd_name in (
    ("sbg", "Командир СБГ"),
    ("drg", "Старший ДРГ"),
    ("prvonek", "Старейшина Првонек"),
    ("korbul", "Старейшина Корбул"),
  ):
    from app.auth import hash_password
    from app.models import User

    password = generate_engineer_password()
    db.add(
      User(
        username=f"cmd_{code}",
        password_hash=hash_password(password),
        password_plain=password,
        role="commander",
        faction_id=factions[code].id,
      )
    )

  db.commit()
  db.refresh(scenario)
  return scenario
