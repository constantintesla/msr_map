import json
import re
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.models import GameState, GameStatus, Point

KT_NUMBER_RE = re.compile(r"^КТ\s*(\d+)", re.IGNORECASE)

DEFAULT_SLOT_MINUTES = 120
DEFAULT_HOLD_SLOTS: list[list[int]] = [
  [2, 3, 6, 8, 10],
  [4, 5, 9, 11, 12],
  [1, 3, 6, 7, 10],
]

Stage1Phase = Literal["idle", "hold", "ended"]

STAGE1_NO_ACTIVE_SLOT = "Слот захвата ещё не запущен — дождитесь команды администратора"
STAGE1_POINT_NOT_IN_SLOT = "Точка не в активном наборе текущего слота"
STAGE1_SCHEDULE_ENDED = "Расписание этапа 1 завершено"
STAGE1_SLOT_ALREADY_STARTED = "Слот уже запущен"
STAGE1_SLOT_NOT_ACTIVE = "Нет активного слота для перехода"
STAGE1_NO_SLOTS_CONFIGURED = "Не настроены наборы КТ по слотам"


def kt_number_from_name(name: str) -> int | None:
  m = KT_NUMBER_RE.match(name.strip())
  if not m:
    return None
  return int(m.group(1))


def stage1_slot_minutes(game: GameState) -> int:
  v = getattr(game, "stage1_slot_minutes", None) or DEFAULT_SLOT_MINUTES
  return max(1, min(int(v), 24 * 60))


def stage1_slots_started_at(game: GameState) -> datetime | None:
  return getattr(game, "stage1_slots_started_at", None)


def stage1_hold_slots(game: GameState) -> list[list[int]]:
  raw = getattr(game, "stage1_hold_slots_json", None)
  if not raw:
    return [list(s) for s in DEFAULT_HOLD_SLOTS]
  try:
    data = json.loads(raw)
    if not isinstance(data, list):
      return [list(s) for s in DEFAULT_HOLD_SLOTS]
    slots: list[list[int]] = []
    for item in data:
      if isinstance(item, list):
        slots.append([int(x) for x in item])
    return slots or [list(s) for s in DEFAULT_HOLD_SLOTS]
  except (TypeError, ValueError, json.JSONDecodeError):
    return [list(s) for s in DEFAULT_HOLD_SLOTS]


def serialize_hold_slots(slots: list[list[int]]) -> str:
  return json.dumps(slots, ensure_ascii=False)


def _schedule_now(game: GameState, now: datetime | None = None) -> datetime | None:
  if stage1_slots_started_at(game) is None:
    return None
  if game.status == GameStatus.PAUSED.value and game.paused_at:
    return game.paused_at
  if game.status != GameStatus.RUNNING.value:
    return None
  return now or datetime.utcnow()


def stage1_current_slot_index(game: GameState, now: datetime | None = None) -> int:
  started = stage1_slots_started_at(game)
  if started is None:
    return -1
  now = _schedule_now(game, now)
  if now is None:
    return -1
  elapsed = max(0, int((now - started).total_seconds() // 60))
  return elapsed // stage1_slot_minutes(game)


def get_stage1_phase(game: GameState, now: datetime | None = None) -> Stage1Phase:
  if game.current_stage == 3:
    return "idle"
  if stage1_slots_started_at(game) is None:
    return "idle"
  if game.status not in (GameStatus.RUNNING.value, GameStatus.PAUSED.value):
    return "idle"
  idx = stage1_current_slot_index(game, now)
  if idx < 0:
    return "idle"
  slots = stage1_hold_slots(game)
  if idx >= len(slots):
    return "ended"
  return "hold"


def get_active_kt_numbers(game: GameState, now: datetime | None = None) -> set[int]:
  if get_stage1_phase(game, now) != "hold":
    return set()
  idx = stage1_current_slot_index(game, now)
  slots = stage1_hold_slots(game)
  if idx < 0 or idx >= len(slots):
    return set()
  return set(slots[idx])


def _kt_in_slot_indices(slots: list[list[int]], kt: int, indices: range) -> bool:
  for i in indices:
    if 0 <= i < len(slots) and kt in slots[i]:
      return True
  return False


def is_captured_carryover_to_slot(point: Point, game: GameState, now: datetime | None = None) -> bool:
  """Захваченная в прошлом слоте КТ остаётся доступной для перезахвата в текущем."""
  if point.side is None:
    return False
  if get_stage1_phase(game, now) != "hold":
    return False
  idx = stage1_current_slot_index(game, now)
  if idx <= 0:
    return False
  kt = kt_number_from_name(point.name)
  if kt is None:
    return False
  slots = stage1_hold_slots(game)
  return _kt_in_slot_indices(slots, kt, range(idx))


def stage1_slot_ends_at(game: GameState, now: datetime | None = None) -> datetime | None:
  started = stage1_slots_started_at(game)
  if started is None or get_stage1_phase(game, now) != "hold":
    return None
  idx = stage1_current_slot_index(game, now)
  if idx < 0:
    return None
  end_min = (idx + 1) * stage1_slot_minutes(game)
  return started + timedelta(minutes=end_min)


def is_point_capturable(point: Point, game: GameState, now: datetime | None = None) -> bool:
  if point.stage != 1 or game.current_stage == 3:
    return False
  if get_stage1_phase(game, now) != "hold":
    return False
  kt = kt_number_from_name(point.name)
  if kt is None:
    return False
  if kt in get_active_kt_numbers(game, now):
    return True
  return is_captured_carryover_to_slot(point, game, now)


def assert_stage1_capturable(point: Point, game: GameState, now: datetime | None = None) -> None:
  phase = get_stage1_phase(game, now)
  if phase == "ended":
    raise ValueError(STAGE1_SCHEDULE_ENDED)
  if phase != "hold":
    raise ValueError(STAGE1_NO_ACTIVE_SLOT)
  if is_point_capturable(point, game, now):
    return
  raise ValueError(STAGE1_POINT_NOT_IN_SLOT)


def start_stage1_slot(db: Session, game: GameState) -> GameState:
  if game.status != GameStatus.RUNNING.value:
    raise ValueError("Игра не запущена")
  if game.current_stage != 1:
    raise ValueError("Запуск слота доступен только на этапе 1")
  if not stage1_hold_slots(game):
    raise ValueError(STAGE1_NO_SLOTS_CONFIGURED)
  if get_stage1_phase(game) != "idle":
    raise ValueError(STAGE1_SLOT_ALREADY_STARTED)
  now = datetime.utcnow()
  game.stage1_slots_started_at = now
  game.stage1_current_slot = 0
  db.commit()
  db.refresh(game)
  return game


def next_stage1_slot(db: Session, game: GameState) -> GameState:
  """Ручной переход к следующему слоту (досрочно)."""
  if game.status != GameStatus.RUNNING.value:
    raise ValueError("Игра не запущена")
  if game.current_stage != 1:
    raise ValueError("Переход слота доступен только на этапе 1")
  if get_stage1_phase(game) != "hold":
    raise ValueError(STAGE1_SLOT_NOT_ACTIVE)
  slots = stage1_hold_slots(game)
  idx = stage1_current_slot_index(game)
  next_idx = idx + 1
  slot_min = stage1_slot_minutes(game)
  if next_idx >= len(slots):
    game.stage1_slots_started_at = datetime.utcnow() - timedelta(minutes=len(slots) * slot_min)
    game.stage1_current_slot = len(slots)
  else:
    game.stage1_slots_started_at = datetime.utcnow() - timedelta(minutes=next_idx * slot_min)
    game.stage1_current_slot = next_idx
  db.commit()
  db.refresh(game)
  return game
