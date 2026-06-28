# 0002: Local-First Deployment

Status: Accepted

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
