"""Pluggable Banshee token verifiers.

A verifier turns a Banshee bearer token into an identity or None.
`dev` accepts one static token from env. Add `oidc` (Banshee SSO introspection)
later by implementing the same interface and registering it in `get_verifier`.
"""
import hmac
from dataclasses import dataclass
from typing import Optional, Protocol

from .config import Settings


@dataclass
class BansheeIdentity:
    account_id: str
    online_id: str


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Optional[BansheeIdentity]: ...


class DevStaticVerifier:
    def __init__(self, s: Settings):
        self.s = s

    def verify(self, token: str) -> Optional[BansheeIdentity]:
        if not self.s.dev_token or not hmac.compare_digest(token, self.s.dev_token):
            return None
        return BansheeIdentity(self.s.dev_account_id, self.s.dev_online_id)


class BansheeSSOVerifier:
    """Stub: will call Banshee SSO (banshee-accounts) token introspection."""

    def __init__(self, s: Settings):
        self.s = s

    def verify(self, token: str) -> Optional[BansheeIdentity]:
        raise NotImplementedError("Banshee SSO verifier not wired yet; use BPN_VERIFIER=dev")


def get_verifier(s: Settings) -> TokenVerifier:
    return {"dev": DevStaticVerifier, "sso": BansheeSSOVerifier}[s.verifier](s)
