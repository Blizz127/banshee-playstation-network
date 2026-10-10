# PS5 Homebrew Client Contract (Banshee PSN, lab)

Contract for a homebrew app on Blizz's jailbroken PS5 that signs in to Banshee PSN and mirrors trophies.
Lab-only: the app talks **only** to the Banshee base URL. It never contacts Sony, and the lab DNS sinkholes Sony domains.

## 1. Transport
- Base URL is configurable in the app's settings file. Default: `https://np.banshee.lan:8460` (the AX41 over Tailscale, `100.77.107.126`).
- TLS 1.2+ only. The app ships a **private Banshee Lab CA bundle** (`banshee-ca.pem`) and trusts *only* that bundle for this host. It doesn't use or change the console's system trust store. Hostname verification stays on.
- JSON bodies, `Content-Type: application/json`, UTF-8. Timestamps are ISO-8601 UTC (`2026-10-10T20:00:00Z`).
- Every request sends `User-Agent: banshee-np-ps5/<version>`.

## 2. Retries
- Retry only on network errors, `429`, and `5xx`. Use exponential backoff of 1s, 2s, 4s, 8s, 16s (cap 30s) with ±20% jitter, at most 6 attempts. Honor `Retry-After`.
- Never retry `400`, `403`, `404` or `422` (fix the request instead). On `401` with a ticket, refresh once (§4), then retry the call once.
- `POST /v1/trophies/sync` is idempotent, so it's safe to resend the full title state after a timeout.
- Queue syncs while offline and flush them when connectivity returns.

## 3. Enrollment (one-time, done by Blizz)
An admin enrolls each console on the server:
```
POST /v1/admin/consoles   X-Admin-Token: <admin>
{"console_id": "ps5-lab-01", "platform": "ps5", "label": "Blizz PS5 11.2"}
-> 201 {"console_id": "ps5-lab-01", "console_secret": "<shown once>"}
```
`console_id` and `console_secret` go into the app's settings file on the console. A console that isn't enrolled, or is disabled, gets `403` everywhere.

## 4. Auth
**Get a ticket.** The Banshee bearer token is the user's Banshee login token (in dev, the static `BPN_DEV_TOKEN`).
```
POST /v1/auth/ticket
Authorization: Bearer <banshee token>
{"console_id": "ps5-lab-01", "console_secret": "<secret>"}
-> 200 {"ticket": "bpn1.<payload>.<sig>", "expires_at": 1760130000,
        "refresh_token": "<opaque>", "account_id": "blizz", "online_id": "Blizz"}
   401 bad Banshee token | 403 console not enrolled / bad secret
```
Send `Authorization: Bearer <ticket>` on every other `/v1/*` call. Tickets last 15 min. Treat the ticket as opaque.

**Refresh.** Refresh when fewer than 60s are left, or after a `401`. Refresh tokens rotate: store the new one and discard the old one, because reuse is rejected.
```
POST /v1/auth/refresh
{"refresh_token": "<opaque>", "console_id": "ps5-lab-01"}
-> 200 (same shape as /v1/auth/ticket)   401 -> redo /v1/auth/ticket
```

**Who am I.** `GET /v1/me` returns `{"account_id","online_id","console_id","ticket_expires_at","status":"online"}`. The test app shows "Signed in as <online_id> — Online".

**Health.** `GET /health` (no auth) returns `{"status":"ok","schema_version":2,...}`.

## 5. Trophy mirroring (retail and homebrew)
Source of data: the app **reads the console's local trophy database read-only** for titles the user has played, and sends what's unlocked. It never writes to console trophy data and never modifies games. (How the local database is accessed in the jailbreak environment is out of scope for this document.)

Send the **full current unlocked set** per title. The server merges it:
```
POST /v1/trophies/sync
Authorization: Bearer <ticket>
{
  "title_id": "PPSA12345",            // CUSA/PPSA/NPWR... code, optional _00 suffix
  "title_name": "Monster Hunter Stories 3",
  "playtime_minutes": 120,             // cumulative; server keeps the max seen
  "trophies": [
    {"id": 1, "name": "First Bond", "grade": "bronze", "unlocked_at": "2026-10-10T20:00:00Z"}
  ]                                    // grade: platinum|gold|silver|bronze; max 4096
}
-> 200 {"title_id": "PPSA12345", "received": 1, "new": 1, "total_unlocked": 1}
   422 validation error (bad title_id, grade, ...)
```
Merge rules: the key is (account, title_id, trophy id). Resending is a no-op, the earliest `unlocked_at` wins, and playtime never goes down. Locked trophies aren't sent.

When to sync: on app start, when a title closes, and every 10 min while running.

`GET /v1/trophies/{online_id|account_id}` returns `{"account_id","online_id","titles":[{"title_id","title_name","playtime_minutes","last_synced_at","trophies":[...]}]}`.

## 6. Presence (now playing)
```
POST /v1/presence   {"title_id": "PPSA12345", "title_name": "Monster Hunter Stories 3", "status": "playing"}
                    status: online|playing|offline
GET  /v1/presence/now-playing
-> {"players": [{"online_id","console_id","title_id","title_name","status","updated_at"}]}
```
Send a heartbeat every 2–5 min while playing (presence expires after 10 min), and send `offline` on exit.
The Banshee launcher reads `now-playing` for the friends list and Who's Online.

## 7. Errors
Errors use FastAPI's shape `{"detail": "..."}` (or a list for 422 validation errors).

## Target environment (Blizz's console, 2026-10-10)
- Firmware 11.2, jailbroken with etaHEN + kstuff. The client ships as an etaHEN-loadable homebrew payload/app.
- Console on home LAN at 192.168.0.227. It reaches the Banshee PSN service over Tailscale or a LAN relay, since the AX41 can't see the home LAN directly.
- Whether the local trophy DB is readable is still to be confirmed by the first test build.
