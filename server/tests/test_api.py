import pytest
from fastapi.testclient import TestClient

from bpn.app import create_app
from bpn.config import Settings

DEV = "dev-banshee-token"
ADMIN = "admin-secret"


@pytest.fixture
def client(tmp_path):
    s = Settings(db_path=str(tmp_path / "t.db"), signing_key="k", admin_token=ADMIN,
                 verifier="dev", dev_token=DEV)
    return TestClient(create_app(s))


def enroll(c, cid="ps5-lab-01"):
    r = c.post("/v1/admin/consoles", json={"console_id": cid}, headers={"X-Admin-Token": ADMIN})
    assert r.status_code == 201
    return r.json()["console_secret"]


def ticket(c, cid="ps5-lab-01", secret=None):
    secret = secret or enroll(c, cid)
    r = c.post("/v1/auth/ticket", json={"console_id": cid, "console_secret": secret},
               headers={"Authorization": f"Bearer {DEV}"})
    assert r.status_code == 200, r.text
    return r.json()


def h(t):
    return {"Authorization": f"Bearer {t['ticket']}"}


def test_health(client):
    r = client.get("/health")
    assert r.json()["status"] == "ok" and r.json()["schema_version"] == 2


def test_ticket_issue_and_me(client):
    t = ticket(client)
    me = client.get("/v1/me", headers=h(t)).json()
    assert me["online_id"] == "Blizz" and me["console_id"] == "ps5-lab-01"


def test_bad_banshee_token(client):
    sec = enroll(client)
    r = client.post("/v1/auth/ticket", json={"console_id": "ps5-lab-01", "console_secret": sec},
                    headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_enrollment_gate(client):
    r = client.post("/v1/auth/ticket", json={"console_id": "unknown-1", "console_secret": "x" * 20},
                    headers={"Authorization": f"Bearer {DEV}"})
    assert r.status_code == 403
    enroll(client)
    r = client.post("/v1/auth/ticket", json={"console_id": "ps5-lab-01", "console_secret": "w" * 20},
                    headers={"Authorization": f"Bearer {DEV}"})
    assert r.status_code == 403  # wrong secret
    assert client.post("/v1/admin/consoles", json={"console_id": "abcd"}).status_code == 403  # no admin


def test_disabled_console_loses_access(client):
    t = ticket(client)
    client.delete("/v1/admin/consoles/ps5-lab-01", headers={"X-Admin-Token": ADMIN})
    assert client.get("/v1/me", headers=h(t)).status_code == 403
    r = client.post("/v1/auth/refresh", json={"refresh_token": t["refresh_token"], "console_id": "ps5-lab-01"})
    assert r.status_code == 401


def test_refresh_rotates(client):
    t = ticket(client)
    body = {"refresh_token": t["refresh_token"], "console_id": "ps5-lab-01"}
    r = client.post("/v1/auth/refresh", json=body)
    assert r.status_code == 200
    t2 = r.json()
    assert t2["refresh_token"] != t["refresh_token"]
    assert client.get("/v1/me", headers=h(t2)).status_code == 200
    assert client.post("/v1/auth/refresh", json=body).status_code == 401  # reuse rejected
    bad = {"refresh_token": t2["refresh_token"], "console_id": "other"}
    assert client.post("/v1/auth/refresh", json=bad).status_code == 401


def test_expired_ticket(client, monkeypatch):
    t = ticket(client)
    import time as _t
    real = _t.time
    monkeypatch.setattr("bpn.tokens.time.time", lambda: real() + 10_000)
    assert client.get("/v1/me", headers=h(t)).status_code == 401


SYNC = {
    "title_id": "PPSA12345",
    "title_name": "Monster Hunter Stories 3",
    "playtime_minutes": 120,
    "trophies": [
        {"id": 1, "name": "First Bond", "grade": "bronze", "unlocked_at": "2026-10-10T20:00:00Z"},
        {"id": 2, "name": "Rider", "grade": "silver", "unlocked_at": "2026-10-10T21:00:00Z"},
    ],
}


def test_trophy_sync_idempotent(client):
    t = ticket(client)
    r1 = client.post("/v1/trophies/sync", json=SYNC, headers=h(t)).json()
    assert r1["new"] == 2 and r1["total_unlocked"] == 2
    r2 = client.post("/v1/trophies/sync", json=SYNC, headers=h(t)).json()
    assert r2["new"] == 0 and r2["total_unlocked"] == 2
    # later sync: one new trophy, lower playtime ignored, later timestamp for old trophy ignored
    later = dict(SYNC, playtime_minutes=90, trophies=SYNC["trophies"] + [
        {"id": 3, "name": "Egg Hunter", "grade": "gold", "unlocked_at": "2026-10-11T01:00:00Z"}])
    later["trophies"][0] = dict(later["trophies"][0], unlocked_at="2026-10-12T00:00:00Z")
    r3 = client.post("/v1/trophies/sync", json=later, headers=h(t)).json()
    assert r3["new"] == 1 and r3["total_unlocked"] == 3
    data = client.get("/v1/trophies/Blizz", headers=h(t)).json()
    title = data["titles"][0]
    assert title["playtime_minutes"] == 120 and len(title["trophies"]) == 3
    assert title["trophies"][0]["unlocked_at"].startswith("2026-10-10T20:00")


def test_trophy_sync_validation(client):
    t = ticket(client)
    assert client.post("/v1/trophies/sync", json=dict(SYNC, title_id="XYZ"), headers=h(t)).status_code == 422
    assert client.post("/v1/trophies/sync", json=SYNC).status_code == 401
    assert client.get("/v1/trophies/nobody", headers=h(t)).status_code == 404


def test_presence(client):
    t = ticket(client)
    client.post("/v1/presence", json={"title_id": "PPSA12345", "title_name": "Monster Hunter Stories 3"},
                headers=h(t))
    p = client.get("/v1/presence/now-playing", headers=h(t)).json()["players"]
    assert p[0]["online_id"] == "Blizz" and p[0]["title_name"] == "Monster Hunter Stories 3"
    client.post("/v1/presence", json={"status": "offline"}, headers=h(t))
    assert client.get("/v1/presence/now-playing", headers=h(t)).json()["players"] == []


def test_migrations_idempotent(tmp_path):
    from bpn import db
    c = db.connect(str(tmp_path / "m.db"))
    assert db.migrate(c) == 2
