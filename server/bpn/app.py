"""Banshee PlayStation Network (lab) — Phase 1 auth + retail trophy mirroring.

Lab-only. This service never contacts, proxies to, or impersonates Sony.
"""
import hmac
import re
import secrets
import time
from datetime import datetime
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from . import db, tokens
from .config import Settings
from .verifier import get_verifier

TITLE_ID_RE = re.compile(r"^(CUSA|PPSA|NPWR|NPUB|NPEB|BLUS|BLES|PCSA|PCSE)\d{5}(_\d{2})?$")


# ---------- models ----------
class TicketRequest(BaseModel):
    console_id: str = Field(min_length=4, max_length=64)
    console_secret: str = Field(min_length=16, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str
    console_id: str


class ConsoleEnroll(BaseModel):
    console_id: str = Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    platform: Literal["ps5", "ps4", "ps3", "vita"] = "ps5"
    label: Optional[str] = None
    console_secret: Optional[str] = Field(default=None, min_length=16)


class Trophy(BaseModel):
    id: int = Field(ge=0, le=4096)
    name: str = Field(min_length=1, max_length=200)
    grade: Literal["platinum", "gold", "silver", "bronze"]
    unlocked_at: datetime


class TrophySync(BaseModel):
    title_id: str
    title_name: str = Field(min_length=1, max_length=200)
    trophies: list[Trophy] = Field(max_length=4096)
    playtime_minutes: int = Field(ge=0)

    @field_validator("title_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        v = v.upper()
        if not TITLE_ID_RE.match(v):
            raise ValueError("title_id must look like PPSA01234 / CUSA01234 (optionally _00)")
        return v


class PresenceUpdate(BaseModel):
    title_id: Optional[str] = None
    title_name: Optional[str] = Field(default=None, max_length=200)
    status: Literal["online", "playing", "offline"] = "playing"


# ---------- app ----------
def create_app(settings: Optional[Settings] = None) -> FastAPI:
    s = settings or Settings()
    conn = db.connect(s.db_path)
    verifier = get_verifier(s)
    app = FastAPI(title="Banshee PlayStation Network (lab)", version="0.1.0")
    app.state.settings, app.state.db = s, conn

    def bearer(authorization: str = Header(default="")) -> str:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        return authorization[7:].strip()

    def ticket_auth(tok: str = Depends(bearer)) -> dict:
        p = tokens.verify_ticket(s.signing_key, tok)
        if not p:
            raise HTTPException(401, "invalid or expired ticket")
        c = conn.execute("SELECT enabled FROM consoles WHERE console_id=?", (p["cid"],)).fetchone()
        if not c or not c["enabled"]:
            raise HTTPException(403, "console not enrolled")
        return p

    def admin(x_admin_token: str = Header(default="")) -> None:
        if not s.admin_token or not hmac.compare_digest(x_admin_token, s.admin_token):
            raise HTTPException(403, "admin token required")

    def check_console(console_id: str, secret: Optional[str]) -> None:
        c = conn.execute("SELECT * FROM consoles WHERE console_id=?", (console_id,)).fetchone()
        if not c or not c["enabled"]:
            raise HTTPException(403, "console not enrolled")
        if secret is not None and not hmac.compare_digest(
                tokens.hash_secret(secret, c["salt"]), c["secret_hash"]):
            raise HTTPException(403, "console not enrolled")

    def new_session(account_id: str, online_id: str, console_id: str) -> dict:
        ticket, exp = tokens.issue_ticket(s.signing_key, account_id, online_id, console_id, s.ticket_ttl)
        refresh = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO refresh_tokens VALUES (?,?,?,?,0)",
                     (tokens.sha256(refresh), account_id, console_id, int(time.time()) + s.refresh_ttl))
        return {"ticket": ticket, "expires_at": exp, "refresh_token": refresh,
                "account_id": account_id, "online_id": online_id}

    @app.get("/health")
    def health():
        v = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        return {"status": "ok", "schema_version": v, "verifier": s.verifier}

    @app.post("/v1/admin/consoles", dependencies=[Depends(admin)], status_code=201)
    def enroll(body: ConsoleEnroll):
        secret = body.console_secret or secrets.token_urlsafe(32)
        salt = secrets.token_hex(16)
        try:
            conn.execute("INSERT INTO consoles VALUES (?,?,?,?,?,1,?)",
                         (body.console_id, tokens.hash_secret(secret, salt), salt,
                          body.platform, body.label, int(time.time())))
        except Exception:
            raise HTTPException(409, "console already enrolled")
        return {"console_id": body.console_id, "console_secret": secret}

    @app.delete("/v1/admin/consoles/{console_id}", dependencies=[Depends(admin)])
    def disable(console_id: str):
        conn.execute("UPDATE consoles SET enabled=0 WHERE console_id=?", (console_id,))
        conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE console_id=?", (console_id,))
        return {"console_id": console_id, "enabled": False}

    @app.post("/v1/auth/ticket")
    def auth_ticket(body: TicketRequest, tok: str = Depends(bearer)):
        ident = verifier.verify(tok)
        if not ident:
            raise HTTPException(401, "invalid Banshee token")
        check_console(body.console_id, body.console_secret)
        conn.execute("INSERT OR IGNORE INTO accounts VALUES (?,?,?)",
                     (ident.account_id, ident.online_id, int(time.time())))
        return new_session(ident.account_id, ident.online_id, body.console_id)

    @app.post("/v1/auth/refresh")
    def auth_refresh(body: RefreshRequest):
        h = tokens.sha256(body.refresh_token)
        r = conn.execute("SELECT * FROM refresh_tokens WHERE token_hash=?", (h,)).fetchone()
        if not r or r["revoked"] or r["expires_at"] < time.time() or r["console_id"] != body.console_id:
            raise HTTPException(401, "invalid refresh token")
        check_console(body.console_id, None)
        conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE token_hash=?", (h,))  # rotate
        a = conn.execute("SELECT * FROM accounts WHERE account_id=?", (r["account_id"],)).fetchone()
        return new_session(a["account_id"], a["online_id"], body.console_id)

    @app.get("/v1/me")
    def me(t: dict = Depends(ticket_auth)):
        return {"account_id": t["sub"], "online_id": t["oid"], "console_id": t["cid"],
                "ticket_expires_at": t["exp"], "status": "online"}

    @app.post("/v1/trophies/sync")
    def trophy_sync(body: TrophySync, t: dict = Depends(ticket_auth)):
        now = int(time.time())
        acct = t["sub"]
        conn.execute("BEGIN")
        try:
            conn.execute(
                """INSERT INTO titles VALUES (?,?,?,?,?)
                   ON CONFLICT(account_id,title_id) DO UPDATE SET
                     title_name=excluded.title_name,
                     playtime_minutes=MAX(titles.playtime_minutes, excluded.playtime_minutes),
                     last_synced_at=excluded.last_synced_at""",
                (acct, body.title_id, body.title_name, body.playtime_minutes, now))
            added = 0
            for tr in body.trophies:
                ts = tr.unlocked_at.isoformat()
                cur = conn.execute(
                    "INSERT OR IGNORE INTO trophies VALUES (?,?,?,?,?,?,?)",
                    (acct, body.title_id, tr.id, tr.name, tr.grade, ts, t["cid"]))
                if cur.rowcount:
                    added += 1
                else:  # keep earliest unlock time; refresh name/grade
                    conn.execute(
                        """UPDATE trophies SET name=?, grade=?, unlocked_at=MIN(unlocked_at, ?)
                           WHERE account_id=? AND title_id=? AND trophy_id=?""",
                        (tr.name, tr.grade, ts, acct, body.title_id, tr.id))
            total = conn.execute("SELECT COUNT(*) FROM trophies WHERE account_id=? AND title_id=?",
                                 (acct, body.title_id)).fetchone()[0]
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return {"title_id": body.title_id, "received": len(body.trophies), "new": added,
                "total_unlocked": total}

    @app.get("/v1/trophies/{user}")
    def trophies_for(user: str, _: dict = Depends(ticket_auth)):
        a = conn.execute("SELECT * FROM accounts WHERE account_id=? OR online_id=?", (user, user)).fetchone()
        if not a:
            raise HTTPException(404, "unknown user")
        out = []
        for ti in conn.execute("SELECT * FROM titles WHERE account_id=? ORDER BY last_synced_at DESC",
                               (a["account_id"],)):
            trs = [dict(id=r["trophy_id"], name=r["name"], grade=r["grade"], unlocked_at=r["unlocked_at"])
                   for r in conn.execute(
                       "SELECT * FROM trophies WHERE account_id=? AND title_id=? ORDER BY unlocked_at",
                       (a["account_id"], ti["title_id"]))]
            out.append(dict(title_id=ti["title_id"], title_name=ti["title_name"],
                            playtime_minutes=ti["playtime_minutes"], last_synced_at=ti["last_synced_at"],
                            trophies=trs))
        return {"account_id": a["account_id"], "online_id": a["online_id"], "titles": out}

    @app.post("/v1/presence")
    def presence(body: PresenceUpdate, t: dict = Depends(ticket_auth)):
        conn.execute("INSERT OR REPLACE INTO presence VALUES (?,?,?,?,?,?)",
                     (t["sub"], t["cid"], body.title_id, body.title_name, body.status, int(time.time())))
        return {"ok": True}

    @app.get("/v1/presence/now-playing")
    def now_playing(_: dict = Depends(ticket_auth)):
        cutoff = int(time.time()) - s.presence_ttl
        rows = conn.execute(
            """SELECT p.*, a.online_id FROM presence p JOIN accounts a USING(account_id)
               WHERE p.updated_at>=? AND p.status!='offline' ORDER BY p.updated_at DESC""", (cutoff,))
        return {"players": [dict(online_id=r["online_id"], console_id=r["console_id"], title_id=r["title_id"],
                                 title_name=r["title_name"], status=r["status"], updated_at=r["updated_at"])
                            for r in rows]}

    return app



def get_app() -> FastAPI:  # uvicorn --factory bpn.app:get_app
    return create_app()
