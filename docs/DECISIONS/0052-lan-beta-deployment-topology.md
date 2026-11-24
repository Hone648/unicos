# 0052. LAN beta deployment topology

## Status

Accepted for the initial single-shop beta.

## Decision

One dedicated Linux PC in the shop hosts Unicos. Docker Compose manages the
application services and PostgreSQL remains the database. Staff use browsers
on the shop LAN. The beta has no public internet exposure. Eventual
internet-hosted deployment remains the direction in
[ADR 0006](0006-web-capable-deployment.md). Development Compose continues to
serve the local development workflow.

## Proposed implementation boundary

Publish only the reverse proxy on the approved shop network. Keep Django and
PostgreSQL on private Compose networking. Restrict access to approved shop
devices and any designated administration network. Treat guest Wi-Fi as
outside that boundary. Disable inbound router forwards, automatic port
mapping, and remote-access tunnels for beta services. Verify effective
Docker, host, and router rules from allowed and disallowed networks,
including IPv6 where enabled. Docker port publishing has its own firewall
behavior. See [Docker's packet filtering and firewall documentation](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

Keep release images and deployment-specific configuration separate so a
future host can reuse the application build. The hosted environment will need
its own network, access, and recovery design.

## Consequences and open choices

The PC, its storage, shop power, and local network can each interrupt service.
The beta has one application host and no automatic failover. The host and
network design must be reviewed before the beta build is reachable by shop
devices. Linux distribution, hardware sizing, network layout, firewall
ownership, and power protection remain open. See
[local recovery](0055-local-backup-and-recovery.md) and
[LAN naming and HTTPS](0054-lan-https-and-service-naming.md).
