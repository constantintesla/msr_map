"""Тесты парсера KML/KMZ."""

from pathlib import Path

from app.kmz_parser import load_preset_game_kml, parse_kml_file

KMZ_DIR = Path(__file__).resolve().parents[2] / "kmz"


class TestKmzParser:
  def test_parse_task2_loot_boxes(self):
    kml_path = KMZ_DIR / "Задача-2.kml"
    if not kml_path.exists():
      return

    points, caches, landmarks = parse_kml_file(kml_path)
    assert not points
    assert len(caches) == 10
    assert all(c.cache_kind == "film_loot" for c in caches)
    assert not landmarks

  def test_parse_task1_control_points(self):
    kml_path = KMZ_DIR / "Задача1.kml"
    if not kml_path.exists():
      return

    points, caches, landmarks = parse_kml_file(kml_path)
    assert len(points) >= 12

  def test_coords_inverted_to_lat_lon(self):
    kml_path = KMZ_DIR / "Задача-2.kml"
    if not kml_path.exists():
      return

    _, caches, _ = parse_kml_file(kml_path)
    first = caches[0]
    # KML: 132.828296,44.529392 → lat≈44.53, lon≈132.83
    assert 44 < first.lat < 45
    assert 132 < first.lon < 133

  def test_load_preset_returns_data(self):
    preset_points, preset_caches, preset_landmarks = load_preset_game_kml(KMZ_DIR)
    assert preset_points or preset_caches or preset_landmarks
