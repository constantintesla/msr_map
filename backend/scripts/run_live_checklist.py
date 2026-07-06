"""Live API checklist against running dev backend."""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
results: list[tuple[str, bool, str]] = []


def wait_health(timeout: int = 30) -> bool:
  for _ in range(timeout):
    try:
      r = httpx.get(f"{BASE}/health", timeout=2)
      if r.status_code == 200:
        return True
    except Exception:
      pass
    time.sleep(1)
  return False


def login(user: str, password: str) -> str:
  r = httpx.post(f"{BASE}/api/auth/login", json={"username": user, "password": password}, timeout=10)
  r.raise_for_status()
  return r.json()["access_token"]


def hdr(token: str) -> dict[str, str]:
  return {"Authorization": f"Bearer {token}"}


def check(name: str, cond: bool, detail: str = "") -> None:
  ok = bool(cond)
  results.append((name, ok, detail))
  mark = "OK" if ok else "FAIL"
  suffix = f" — {detail}" if detail else ""
  print(f"[{mark}] {name}{suffix}")


def main() -> int:
  if not wait_health():
    print("Backend not ready at", BASE)
    return 1

  admin = login("admin", "admin")
  eng_a = login("eng_a1", "alfa01")
  eng_b = login("eng_b1", "bravo1")

  httpx.post(f"{BASE}/api/admin/game/reset", headers=hdr(admin))
  httpx.post(f"{BASE}/api/admin/kml/reload", headers=hdr(admin))
  httpx.patch(
    f"{BASE}/api/admin/settings",
    headers=hdr(admin),
    json={
      "engineers_per_side_a": 5,
      "engineers_per_side_b": 5,
      "capture_radius_m": 15,
      "disable_capture_distance": True,
      "point_capture_seconds": 30,
      "point_hold_ping_seconds": 30,
      "post_hold_seconds": 60,
      "post_hold_ping_seconds": 30,
      "stage2_issue_interval_minutes": 60,
      "stage2_issue_mode": "sequential",
    },
  )
  httpx.post(f"{BASE}/api/admin/game/start", headers=hdr(admin))
  httpx.post(f"{BASE}/api/admin/game/stage/1", headers=hdr(admin))

  status = httpx.get(f"{BASE}/api/status", timeout=10).json()
  point = status.get("points", [None])[0]
  check("stage1: game running with CT", point is not None, f"point_id={point['id'] if point else None}")

  if not point:
    return 1

  pid = point["id"]
  code = f"{4000 + pid:04d}"[-4:]
  lat, lon = point["lat"], point["lon"]

  r = httpx.post(
    f"{BASE}/api/point/begin-capture",
    headers=hdr(eng_a),
    json={"point_id": pid, "side": "A", "code": "0000", "lat": lat, "lon": lon},
  )
  check("stage1: wrong code -> 400", r.status_code == 400, r.text[:120])

  r = httpx.post(
    f"{BASE}/api/point/begin-capture",
    headers=hdr(eng_a),
    json={"point_id": pid, "side": "A", "code": code, "lat": lat, "lon": lon},
  )
  check("stage1: begin capture", r.status_code == 200, r.text[:120])

  r = httpx.post(
    f"{BASE}/api/point/begin-capture",
    headers=hdr(eng_b),
    json={"point_id": pid, "side": "B", "code": code, "lat": lat, "lon": lon},
  )
  check("stage1: other side blocked", r.status_code in (400, 403), r.text[:120])

  print("... waiting 31s for capture timer")
  time.sleep(31)
  r = httpx.post(
    f"{BASE}/api/hold/confirm",
    headers=hdr(eng_a),
    json={"point_id": pid, "side": "A"},
  )
  check(
    "stage1: capture via hold/confirm",
    r.status_code == 200 and r.json().get("hold_ready"),
    r.text[:160],
  )

  status = httpx.get(f"{BASE}/api/status").json()
  captured = next((p for p in status["points"] if p["id"] == pid), {})
  check("stage1: point captured by A", captured.get("side") == "A", str(captured.get("side")))

  r = httpx.post(
    f"{BASE}/api/point/begin-capture",
    headers=hdr(eng_b),
    json={"point_id": pid, "side": "B", "code": code, "lat": lat, "lon": lon},
  )
  check("stage1: re-capture rejected", r.status_code == 400, r.text[:120])

  httpx.post(f"{BASE}/api/admin/game/pause", headers=hdr(admin))
  r = httpx.post(
    f"{BASE}/api/point/begin-capture",
    headers=hdr(eng_a),
    json={"point_id": pid, "side": "A", "code": code, "lat": lat, "lon": lon},
  )
  check("stage1: pause blocks capture", r.status_code == 400, r.text[:120])
  httpx.post(f"{BASE}/api/admin/game/start", headers=hdr(admin))

  httpx.post(f"{BASE}/api/admin/game/stage/2", headers=hdr(admin))
  httpx.post(f"{BASE}/api/admin/stage2/issue", headers=hdr(admin))
  status = httpx.get(f"{BASE}/api/status").json()
  loot = status.get("caches", [None])[0]
  check("stage2: loot issued", loot is not None, f"cache_id={loot['id'] if loot else None}")

  if loot:
    cid = loot["id"]
    fake_video = ("report.mp4", b"\x00" * 256, "video/mp4")
    r = httpx.post(
      f"{BASE}/api/cache/film-report",
      headers=hdr(eng_a),
      data={"cache_id": cid, "side": "A", "lat": loot["lat"], "lon": loot["lon"]},
      files={"file": fake_video},
    )
    check("stage2: film report by A", r.status_code == 200, r.text[:120])

    bases = status.get("landmarks", [])
    base_a = next(
      (b for b in bases if b.get("team_side") == "A" and b.get("kind") in ("base", "base_start")),
      None,
    )
    fake_jpg = ("base.jpg", b"\xff\xd8\xff" + b"\x00" * 256, "image/jpeg")
    if base_a:
      r = httpx.post(
        f"{BASE}/api/cache/deliver-report",
        headers=hdr(eng_b),
        data={"cache_id": cid, "side": "B", "lat": base_a["lat"], "lon": base_a["lon"]},
        files={"file": fake_jpg},
      )
      check("stage2: deliver wrong side -> 403", r.status_code == 403, r.text[:120])
      r = httpx.post(
        f"{BASE}/api/cache/deliver-report",
        headers=hdr(eng_a),
        data={"cache_id": cid, "side": "A", "lat": base_a["lat"], "lon": base_a["lon"]},
        files={"file": fake_jpg},
      )
      check("stage2: deliver photo at base A", r.status_code == 200, r.text[:120])
      r = httpx.post(f"{BASE}/api/admin/cache/{cid}/confirm-delivery", headers=hdr(admin))
      check("stage2: admin confirm delivery", r.status_code == 200, r.text[:120])
    else:
      check("stage2: base A exists", False, "no landmark")

  httpx.post(f"{BASE}/api/admin/game/stage/3", headers=hdr(admin))
  status = httpx.get(f"{BASE}/api/status").json()
  post = next((p for p in status.get("points", []) if not p.get("destroyed")), None)
  check("stage3: post found", post is not None, f"post_id={post['id'] if post else None}")

  if post:
    post_id = post["id"]
    mission = httpx.get(f"{BASE}/api/admin/stage1/mission", headers=hdr(admin)).json()
    post_mission = next((m for m in mission if m.get("id") == post_id), None)
    dcode = (post_mission or {}).get("code") or f"{3000 + post_id:04d}"[-4:]
    r = httpx.post(
      f"{BASE}/api/hold/confirm",
      headers=hdr(eng_b),
      json={"point_id": post_id, "side": "B"},
    )
    check("stage3: hold B -> 403", r.status_code == 403, r.text[:120])

    r = httpx.post(
      f"{BASE}/api/point/begin-capture",
      headers=hdr(eng_a),
      json={"point_id": post_id, "side": "A", "code": dcode, "lat": post["lat"], "lon": post["lon"]},
    )
    check("stage3: begin assault", r.status_code == 200, r.text[:120])

    print("... waiting 61s for post hold (with mid ping)")
    time.sleep(30)
    httpx.post(
      f"{BASE}/api/hold/confirm",
      headers=hdr(eng_a),
      json={"point_id": post_id, "side": "A"},
    )
    time.sleep(31)
    r = httpx.post(
      f"{BASE}/api/hold/confirm",
      headers=hdr(eng_a),
      json={"point_id": post_id, "side": "A"},
    )
    check("stage3: hold_ready", r.status_code == 200 and r.json().get("hold_ready"), r.text[:160])

    fake_mp4 = ("report.mp4", b"\x00" * 256, "video/mp4")
    r = httpx.post(
      f"{BASE}/api/point/post-film-report",
      headers=hdr(eng_a),
      data={"point_id": post_id, "side": "A", "lat": post["lat"], "lon": post["lon"]},
      files={"file": fake_mp4},
    )
    check("stage3: post film report A", r.status_code == 200, r.text[:120])

  passed = sum(1 for _, ok, _ in results if ok)
  failed = sum(1 for _, ok, _ in results if not ok)
  print(f"\n=== Total: {passed} OK, {failed} FAIL / {len(results)} ===")
  return 1 if failed else 0


if __name__ == "__main__":
  sys.exit(main())
