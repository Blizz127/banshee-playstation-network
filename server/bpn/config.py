"""Settings from environment. Lab-only service; never talks to Sony."""
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("BPN_DB_PATH", "bpn.sqlite3"))
    signing_key: str = field(default_factory=lambda: os.environ.get("BPN_SIGNING_KEY", "dev-insecure-signing-key"))
    admin_token: str = field(default_factory=lambda: os.environ.get("BPN_ADMIN_TOKEN", ""))
    verifier: str = field(default_factory=lambda: os.environ.get("BPN_VERIFIER", "dev"))
    dev_token: str = field(default_factory=lambda: os.environ.get("BPN_DEV_TOKEN", ""))
    dev_account_id: str = field(default_factory=lambda: os.environ.get("BPN_DEV_ACCOUNT_ID", "blizz"))
    dev_online_id: str = field(default_factory=lambda: os.environ.get("BPN_DEV_ONLINE_ID", "Blizz"))
    ticket_ttl: int = field(default_factory=lambda: int(os.environ.get("BPN_TICKET_TTL", "900")))
    refresh_ttl: int = field(default_factory=lambda: int(os.environ.get("BPN_REFRESH_TTL", str(30 * 86400))))
    presence_ttl: int = field(default_factory=lambda: int(os.environ.get("BPN_PRESENCE_TTL", "600")))
