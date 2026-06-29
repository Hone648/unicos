# 0025: CI Hardening

Status: Accepted

Decision:

Harden GitHub Actions so pull requests must pass both PostgreSQL-backed Django
validation and a Docker runtime smoke check.

Rationale:

- CI now checks for missing migrations with `makemigrations --check`.
- CI now verifies migrations apply with `migrate --noinput`.
- CI now builds the Docker image.
- CI now boots the app with Docker Compose.
- CI now checks `/healthz/`, proving the app can reach the configured database.
- Python/PostgreSQL tests remain the primary full test suite.
- Docker smoke does not run the full test suite again to avoid redundant runtime
  cost.

Scope:

- No runtime app behavior changed.
- No model migration was added.
- No new linting, coverage, security scanning, deployment pipeline, or frontend
  tooling was introduced.
