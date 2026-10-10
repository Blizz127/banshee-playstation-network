# Banshee PSN-Emu — Private Design Brief (DRAFT, private)

Scope: a private home-lab "PSN-like" auth + services stack for Blizz's own, already-jailbroken PS5 (FW 13.60), used for homebrew and self-hosted/offline multiplayer. Hard rules: never connect to, impersonate, or attack Sony's live PSN; no exploits/payloads/kernel patches/DRM bypass/piracy; no Sony keys or credentials; no RE walkthroughs of protected binaries. Public, high-level info only.

## 1. What homebrew on a jailbroken PS5 expects from "network" (high level)
- Retail system software talks to Sony's servers over TLS with pinned/Sony-signed trust. Faithfully emulating *retail* PSN sign-in for retail games is out of scope (it would need Sony keys/protocol RE, which we exclude).
- Realistic target: **our own homebrew/ports** (and Banshee-launched content) that call a **Banshee "network" SDK/API** we define, modeled on PSN concepts:
  - Auth: sign-in → opaque session ticket/token (JWT), account id, online id (display name).
  - Profile/friends stub: friends list, blocked list, avatars.
  - Presence: online/offline, "currently playing", rich status.
  - Matchmaking: rooms/lobbies, join/leave, P2P or relay signaling.
  - Trophies (our own "achievements") and save/cloud storage at a high level (per-title blob store).
  - Leaderboards/scoreboards.
- These map 1:1 to the concept set RPCN implements for PS3 (rooms, scoreboards, title user storage), which is the best public reference model.

## 2. Existing open/community projects
| Project | What | Status | Relevance to PS5 13.60 |
|---|---|---|---|
| **RPCN** (github.com/RipleyTom/rpcn, Rust, AGPL-3.0) | PSN-style server for RPCS3: accounts, friends, presence, rooms/matchmaking, scoreboards, cloud saves | Active, mature | Best architecture reference; README states it does **not** work with real PS3s. Concepts/schema reusable, not wire-compatible with PS5. |
| **RPCS3 Netplay / custom IP-host switches** (wiki.rpcs3.net Help:Netplay) | Emulator-side redirect of game hosts to fan servers | Mature | Model for our "host switch" pointing config. |
| **shadPS4** (PS4 emu, GPL-2.0) | PS4 emulator | Active; networking limited | Future: if it gains NP HLE, a Banshee backend could serve it too. |
| **Kyty / KytyPlus** (PS4/PS5 emu) | Early PS5 emulation | Experimental; network not implemented | Low near-term relevance. |
| Game-specific revival servers (e.g. community PS3/PS4 title servers) | Per-game private servers | Varies | Pattern for Phase 3 (one title at a time). |
- No public open-source PS5 "private PSN" server was found. Banshee would be first-of-kind for its own homebrew; don't expect retail compatibility.

## 3. Pointing methods (high level only)
- **Router/LAN DNS** (Pi-hole/Unbound/dnsmasq on LAN or Tailscale): resolve Banshee service names (e.g. `np.banshee.lan`) to AX41. Also useful to **block** Sony domains so the lab console never reaches live PSN.
- **Console custom DNS** in network settings pointing at the Banshee resolver.
- **Hosts-style redirects inside the jailbreak/homebrew environment**, configured via the homebrew's own settings file — no exploit detail here; use whatever the existing environment already supports.
- Preferred: homebrew uses a **configurable base URL** (like RPCS3's RPCN host setting) so no redirection tricks are needed at all.

## 4. Proposed Banshee architecture
- **Host:** AX41 (Docker compose, behind existing reverse proxy; reach via Tailscale first, public later if ever).
- **Services (start minimal):**
  1. `np-auth` — sign-in with Banshee SSO (OIDC), issues short-lived signed JWT ticket {account_id, online_id, scopes, exp}; refresh tokens.
  2. `np-presence` — WebSocket; online status + now-playing.
  3. `np-social` — friends/blocks (Postgres).
  4. `np-match` — rooms/lobbies + relay/signaling (can borrow RPCN's room model).
  5. `np-storage` — trophies/achievements + per-title save blobs (S3-compatible/MinIO).
- **Client side:** a small homebrew-side library ("banshee-np") with sign-in/ticket/presence calls; Banshee launcher shows the same presence.
- **TLS/certs:** private **Banshee Lab CA**; services get certs from it (step-ca). The homebrew lib pins/trusts the Banshee CA bundle it ships with — no modifying system trust stores via exploit. Keep the CA key offline; short cert lifetimes.
- **Account model:** Banshee SSO account is source of truth; `np_account` row per SSO user (account_id = stable UUID, online_id = unique handle), optional per-console device id registration so a console must be enrolled by Blizz before it can sign in.
- **Safety:** DNS sinkhole for Sony domains on the lab network; no forwarding/proxying to Sony ever.

## 5. Phased plan
- **Phase 0 – research/spike (1 wk):** confirm what the existing 13.60 environment's homebrew can do network-wise (HTTP/TLS libs, custom CA, settings files); stand up DNS + step-ca on AX41; study RPCN data model.
- **Phase 1 – auth stub (MVP):** SSO → `np-auth` → JWT ticket → homebrew test app shows "Signed in as <online_id> — Online". Plus `/me`, health check, token refresh, device enrollment.
- **Phase 2 – presence/friends:** WebSocket presence, friend requests, launcher integration.
- **Phase 3 – matchmaking for one title:** pick one homebrew/port with multiplayer; rooms + relay; measure latency over Tailscale.
- **Phase 4 – trophies/saves:** achievement definitions per title, unlock API, save blob sync with versioning/conflict rules.
- **Risks:** retail titles won't work (by design); PS5 homebrew networking stack constraints; firmware/environment fragility; TLS trust in homebrew; scope creep toward retail-PSN emulation (reject).
- **Legal/ToS note:** private lab on owned hardware only; no Sony services, keys, or content; no distribution of copyrighted material; jailbreaking itself may breach Sony ToS — keep the console off live PSN entirely.

## 6. Open questions for Blizz
1. Which titles first — homebrew/ports you're building, or specific games? (Retail PSN-game compatibility isn't in scope.)
2. PS5-only, or multi-gen (PS3 via RPCN-compatible, PS4/shadPS4, Vita)?
3. Is a 13.60 jailbreak environment already running, and what homebrew loader/network capabilities does it have?
4. Tie to Banshee SSO only, or also allow local-only lab accounts?
5. LAN/Tailscale only, or eventually reachable by friends over the internet?
6. Should presence show in the Banshee launcher from Phase 2?
