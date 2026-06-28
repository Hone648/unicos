# 0004: Docker Build Hygiene

Status: Accepted

Decision:

Add a root `.dockerignore` to keep local secrets, caches, virtual environments,
media files, backups, editor files, and generated artifacts out of the Docker
build context.

Rationale:

- `.env` contains local secrets and environment-specific configuration. It must
  not be sent to Docker build context or copied into an image.
- Build context should stay small and predictable so local-only files do not
  affect builds.
- This matters before auth and business data are added, because later slices
  will introduce more sensitive configuration and operational artifacts.

`.env.example` is a safe template and is intentionally allowed in the Docker
build context. It must not contain real secrets.
