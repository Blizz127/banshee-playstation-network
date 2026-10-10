"""Short-lived HMAC-signed tickets (compact, JWT-like, stdlib only)."""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_ticket(key: str, account_id: str, online_id: str, console_id: str, ttl: int) -> tuple[str, int]:
    exp = int(time.time()) + ttl
    payload = {"v": 1, "sub": account_id, "oid": online_id, "cid": console_id,
               "exp": exp, "jti": secrets.token_hex(8)}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())
    return f"bpn1.{body}.{sig}", exp


def verify_ticket(key: str, ticket: str) -> Optional[dict]:
    try:
        prefix, body, sig = ticket.split(".")
        if prefix != "bpn1":
            return None
        want = _b64(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, want):
            return None
        payload = json.loads(_unb64(body))
        if payload["exp"] < time.time():
            return None
        return payload
    except Exception:
        return None


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def hash_secret(secret: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt.encode(), 100_000).hex()
