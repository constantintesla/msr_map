"""Тесты загрузки буквенно-цифровой сетки из map.kmz."""

import os
from pathlib import Path

from app.map_grid import ensure_map_grid_assets, parse_ground_overlay_from_kml

KMZ_DIR = Path(__file__).resolve().parents[2] / "kmz"


class TestMapGrid:
  def test_parse_ground_overlay_from_map_kmz(self):
    kmz_path = KMZ_DIR / "map.kmz"
    if not kmz_path.exists():
      return

    import zipfile

    with zipfile.ZipFile(kmz_path) as zf:
      kml_name = next(n for n in zf.namelist() if n.lower().endswith(".kml"))
      overlay = parse_ground_overlay_from_kml(zf.read(kml_name))

    assert overlay is not None
    assert overlay.north > overlay.south
    assert overlay.east > overlay.west
    assert 44 < overlay.south < overlay.north < 45
    assert 132 < overlay.west < overlay.east < 133

  def test_ensure_map_grid_assets(self):
    kmz_path = KMZ_DIR / "map.kmz"
    if not kmz_path.exists():
      return

    overlay, image_path = ensure_map_grid_assets(KMZ_DIR)
    assert overlay is not None
    assert image_path is not None
    assert image_path.is_file()
    assert image_path.name == "grid_overlay.png"

  def test_default_kmz_dir_docker_layout(self):
    fake_file = Path("/app/app/map_grid.py")
    backend_root = fake_file.parents[1]
    assert backend_root.as_posix() == "/app"
    assert (backend_root / "kmz").as_posix() == "/app/kmz"

  def test_ensure_with_readonly_kmz_dir(self, tmp_path):
    import shutil

    from app.map_grid import ensure_map_grid_assets

    src_kmz = KMZ_DIR / "map.kmz"
    if not src_kmz.exists():
      return

    ro_dir = tmp_path / "kmz"
    ro_dir.mkdir()
    shutil.copy(src_kmz, ro_dir / "map.kmz")
    os.chmod(ro_dir, 0o555)

    try:
      overlay, image_path = ensure_map_grid_assets(ro_dir)
      assert overlay is not None
      assert image_path is not None
      assert image_path.is_file()
    finally:
      os.chmod(ro_dir, 0o755)

  def test_map_grid_api(self):
    kmz_path = KMZ_DIR / "map.kmz"
    if not kmz_path.exists():
      return

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    res = client.get("/api/map/grid")
    assert res.status_code == 200
    data = res.json()
    assert data is not None
    assert data["image_url"] == "/api/map/grid/image"
    assert data["north"] > data["south"]

    img = client.get("/api/map/grid/image")
    assert img.status_code == 200
    assert img.headers["content-type"].startswith("image/png")
