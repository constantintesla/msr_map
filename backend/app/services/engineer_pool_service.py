"""Пул инженеров на мероприятие — создаётся по настройкам штаба."""

import re
import secrets
import string

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import EngineerLocation, GameState, User

ENGINEER_USERNAME_RE = re.compile(r"^eng_[ab](\d+)$", re.IGNORECASE)
DEFAULT_ENGINEERS_PER_SIDE = 5
PASSWORD_ALPHABET = string.ascii_letters + string.digits
# eng_a1 / eng_b1 — тестовые учётки с фиксированным паролем (6 символов)
DEMO_ENGINEER_PASSWORD = {"A": "alfa01", "B": "bravo1"}


def generate_engineer_password(length: int = 6) -> str:
  return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def password_for_engineer_slot(side: str, slot: int) -> str:
  if slot == 1:
    return DEMO_ENGINEER_PASSWORD[side]
  return generate_engineer_password()


def engineer_password_hint(user: User) -> str:
  return user.password_plain or "—"


def _game_state(db: Session) -> GameState:
  from app.services.scenario_service import get_active_scenario_id

  scenario_id = get_active_scenario_id(db)
  gs = db.query(GameState).filter(GameState.id == scenario_id).first()
  if gs is None:
    gs = GameState(id=scenario_id)
    db.add(gs)
    db.flush()
  return gs


def get_engineers_per_side(db: Session) -> tuple[int, int]:
  gs = _game_state(db)
  a = gs.engineers_per_side_a or DEFAULT_ENGINEERS_PER_SIDE
  b = gs.engineers_per_side_b or DEFAULT_ENGINEERS_PER_SIDE
  return max(1, min(a, 50)), max(1, min(b, 50))


def _engineer_number(username: str) -> int | None:
  m = ENGINEER_USERNAME_RE.match(username)
  return int(m.group(1)) if m else None


def _purge_legacy_engineers(db: Session) -> None:
  """Удаляет старые учётки ing_*, loot_*, post_* (привязанные к точкам)."""
  legacy = (
    db.query(User)
    .filter(User.role == "engineer")
    .filter(
      User.username.like("ing_%")
      | User.username.like("loot_%")
      | User.username.like("post_%")
    )
    .all()
  )
  for user in legacy:
    db.query(EngineerLocation).filter(EngineerLocation.user_id == user.id).delete()
    db.delete(user)
  if legacy:
    db.flush()


def _assign_password(user: User, side: str, slot: int) -> None:
  password = password_for_engineer_slot(side, slot)
  user.password_plain = password
  user.password_hash = hash_password(password)


def list_pool_engineers(db: Session) -> list[User]:
  return (
    db.query(User)
    .filter(User.role == "engineer")
    .filter(User.username.like("eng_a%") | User.username.like("eng_b%"))
    .order_by(User.side, User.username)
    .all()
  )


def sync_engineer_pool(db: Session, *, purge_legacy: bool = False) -> dict[str, int]:
  """Синхронизирует eng_a* / eng_b* с настройками game_state."""
  if purge_legacy:
    _purge_legacy_engineers(db)

  count_a, count_b = get_engineers_per_side(db)
  created = 0
  removed = 0
  backfilled = 0

  for side, count, prefix in [("A", count_a, "eng_a"), ("B", count_b, "eng_b")]:
    existing = (
      db.query(User)
      .filter(User.role == "engineer", User.side == side)
      .filter(User.username.like(f"{prefix}%"))
      .all()
    )
    by_num = {_engineer_number(u.username): u for u in existing if _engineer_number(u.username)}

    for num in list(by_num):
      if num is None or num > count:
        user = by_num[num]
        db.query(EngineerLocation).filter(EngineerLocation.user_id == user.id).delete()
        db.delete(user)
        removed += 1
        del by_num[num]

    for i in range(1, count + 1):
      if i in by_num:
        user = by_num[i]
        if not user.password_plain:
          _assign_password(user, side, i)
          backfilled += 1
        continue
      username = f"{prefix}{i}"
      password = password_for_engineer_slot(side, i)
      db.add(
        User(
          username=username,
          password_hash=hash_password(password),
          password_plain=password,
          role="engineer",
          side=side,
          point_id=None,
          cache_id=None,
        )
      )
      created += 1

  db.flush()
  return {
    "created": created,
    "removed": removed,
    "backfilled": backfilled,
    "side_a": count_a,
    "side_b": count_b,
  }
