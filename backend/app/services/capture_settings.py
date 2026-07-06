from app.models import GameState

DEFAULT_CAPTURE_RADIUS_M = 10
DEFAULT_POINT_CAPTURE_SECONDS = 120
DEFAULT_GPS_ACCURACY_BONUS_MAX_M = 20


def capture_radius_m(game: GameState) -> int:
  r = game.capture_radius_m or DEFAULT_CAPTURE_RADIUS_M
  return max(1, min(int(r), 500))


def capture_distance_disabled(game: GameState) -> bool:
  return bool(game.disable_capture_distance)


def stage1_recapturable(game: GameState | None) -> bool:
  if game is None:
    return True
  return bool(getattr(game, "stage1_recapturable", True))


def point_capture_seconds(game: GameState) -> int:
  s = game.point_capture_seconds or DEFAULT_POINT_CAPTURE_SECONDS
  return max(30, min(int(s), 3600))


def point_hold_ping_seconds(game: GameState) -> int:
  """Интервал кнопки «Подтвердить удержание» на этапе 1."""
  s = getattr(game, "point_hold_ping_seconds", None) or 120
  return max(15, min(int(s), 3600))


def post_hold_seconds(game: GameState) -> int:
  """Время непрерывного удержания поста на этапе 3."""
  s = getattr(game, "post_hold_seconds", None) or 600
  return max(60, min(int(s), 7200))


def post_hold_ping_seconds(game: GameState) -> int:
  """Интервал кнопки «Подтвердить удержание» на этапе 3."""
  s = getattr(game, "post_hold_ping_seconds", None) or 120
  return max(15, min(int(s), 3600))


def gps_accuracy_bonus_max_m(game: GameState | None) -> int:
  if game is None:
    return DEFAULT_GPS_ACCURACY_BONUS_MAX_M
  v = getattr(game, "gps_accuracy_bonus_max_m", None)
  if v is None:
    return DEFAULT_GPS_ACCURACY_BONUS_MAX_M
  return max(0, min(int(v), 100))


def gps_min_accuracy_for_capture_m(game: GameState | None) -> int:
  if game is None:
    return 0
  v = getattr(game, "gps_min_accuracy_for_capture_m", None)
  if v is None:
    return 0
  return max(0, min(int(v), 200))


def gps_lat_offset(game: GameState | None) -> float:
  if game is None:
    return 0.0
  return float(getattr(game, "gps_lat_offset", 0.0) or 0.0)


def gps_lon_offset(game: GameState | None) -> float:
  if game is None:
    return 0.0
  return float(getattr(game, "gps_lon_offset", 0.0) or 0.0)
