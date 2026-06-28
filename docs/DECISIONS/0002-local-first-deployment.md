# 0002: Local-First Deployment

Status: Superseded by 0006-web-capable-deployment

> **Note (revised):** LAN-only / local-network-first is no longer the primary
> deployment assumption. The intended shop has internet access, so the app is
> now expected to become web-accessible / hosted. Local Docker remains the
> development workflow. The original context below is kept for history; see
> `0006-web-capable-deployment.md` for the current direction.

Decision:

Start with LAN/local-network-first deployment while keeping a future web path.

Rationale:

- The first real users are expected to work inside the shop network.
- Local-first deployment reduces early hosting and remote-access complexity.
- The architecture should still avoid choices that block future private remote
  access or public web deployment.

Possible progression:

1. LAN only
2. Tailscale/private remote access
3. Public HTTPS deployment only if needed
