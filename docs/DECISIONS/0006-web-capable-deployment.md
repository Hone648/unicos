# 0006: Web-Capable Deployment

Status: Accepted (supersedes 0002-local-first-deployment)

Decision:

Frame Unicos as a web-based app expected to become internet-accessible /
hosted. Local Docker Compose remains the current development workflow. Public
hosting is not implemented in Slice 2.

Context:

- The intended shop has internet access.
- The earlier local-network-first assumption (ADR 0002) no longer reflects the
  intended deployment. LAN-only is no longer the primary target.

Implications:

- Architecture and docs should describe local Docker development now and a
  web-capable / hosted deployment path later.
- Production deployment will require, before going live:
  - HTTPS
  - Secure Django settings (e.g. `DEBUG=False`, secure cookies, HSTS)
  - Proper `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
  - Database backups
  - Admin hardening
  - File/media storage planning
  - Logging / monitoring

Out of scope for Slice 2:

- Production hosting implementation
- Reverse proxy (Caddy/Nginx)
- HTTPS configuration
- Object storage, email, deployment automation
