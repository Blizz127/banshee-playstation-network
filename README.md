# banshee-playstation-network
Private Banshee PlayStation Network lab stack (homebrew auth, friends, trophies). Never talks to Sony live PSN.

Private lab "Banshee PlayStation Network": Banshee sign-in for PS5 homebrew plus retail trophy mirroring. Lab-only; never talks to Sony.
See `docs/SCOPE.md`, `docs/PSN-EMU-DESIGN.md`, and the client contract in `client-spec/PS5-HOMEBREW-CLIENT.md`.

## Server (Phase 1 + trophy mirroring)
```
cd server
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # tests
BPN_DEV_TOKEN=devtok BPN_ADMIN_TOKEN=admin BPN_SIGNING_KEY=change-me \
  uvicorn --factory bpn.app:get_app --port 8460   # run locally
```
Endpoints: `GET /health`, `POST /v1/auth/ticket`, `POST /v1/auth/refresh`, `GET /v1/me`,
`POST /v1/trophies/sync`, `GET /v1/trophies/{user}`, `POST /v1/presence`, `GET /v1/presence/now-playing`,
plus admin `POST/DELETE /v1/admin/consoles` (enrollment, `X-Admin-Token`).

## Deploy (AX41, Tailscale-only — not deployed yet)
`deploy/Dockerfile` and `deploy/compose.snippet.yml` (binds `100.77.107.126:8460`).
