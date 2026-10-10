# Scope (decided 2026-10-10)

- **Multi-gen plan, PS5 first.** One Banshee account and friends graph (Banshee SSO) shared across PS5, PS4, Vita and PS3.
- **PS5 (first):** a homebrew client or plugin on the 11.2 jailbroken console talks to the Banshee PSN services. It is NOT a replacement for the system PSN sign-in, and retail PSN titles are out of scope.
- **PS3:** an RPCN-style server (the open-source PSN-style server used by the RPCS3 emulator) is the model and possible base.
- **PS4 / Vita:** homebrew clients that use the same service APIs.
- Lab-only. The lab's DNS blocks Sony's domains, and nothing ever talks to Sony's live PSN.

## Phase order
1. Auth: Banshee login, then a short-lived ticket, plus whoami, refresh and health endpoints (on the AX41, over Tailscale).
2. Presence and friends, bridged into the Banshee launcher.
3. Rooms and matchmaking for one homebrew title.
4. Trophies and save sync, tracked by Banshee.
