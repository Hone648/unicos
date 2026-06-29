# Unicos

Unicos is a web-based body shop repair order management app. Local development
runs on Docker Compose; the intended shop has internet access, so a future
internet-accessible hosted deployment is planned (not implemented yet). This
slice adds the accounts/auth baseline on top of the Django, PostgreSQL, Docker,
and CI foundation.

## Stack

- Django
- PostgreSQL
- Docker Compose
- GitHub Actions

## Local Setup

Create a local environment file:

```powershell
Copy-Item .env.example .env
```

`.env` is for local secrets and environment-specific configuration. Do not
commit it. `.dockerignore` keeps local secrets, caches, virtual environments,
media, and generated files out of the Docker build context. The safe
`.env.example` template is intentionally allowed in the build context.

Start the app and database:

```powershell
docker compose up --build
```

The health check should be available at:

```text
http://localhost:8000/healthz/
```

## Development Commands

Run Django checks:

```powershell
docker compose exec web python app/manage.py check
```

Check for missing migrations:

```powershell
docker compose exec web python app/manage.py makemigrations --check
```

Apply migrations:

```powershell
docker compose exec web python app/manage.py migrate --noinput
```

Run tests:

```powershell
docker compose exec web python app/manage.py test
```

For non-Docker local runs, install `requirements.txt` and provide the same
environment variables shown in `.env.example`.

## CI Validation

GitHub Actions runs a PostgreSQL-backed Django test job and a separate Docker
smoke job. CI checks Django system checks, missing migrations, migration
application, the full test suite, Docker image build, Docker Compose startup,
and `/healthz/`.

## Authentication

The app now has a login/logout baseline backed by a custom user model
(`accounts.User`).

- `/` is an authenticated dashboard. Unauthenticated visitors are redirected to
  `/accounts/login/?next=/`.
- `/accounts/login/` and `/accounts/logout/` handle sign in and sign out.
- `/healthz/` remains public.

Create a superuser to sign in and reach the dashboard or Django admin:

```powershell
docker compose exec web python app/manage.py createsuperuser
```

Baseline staff role groups (`Owner/Admin`, `Manager`, `Front Desk`,
`Estimator`, `Technician`, `Read-only`) are created automatically by a data
migration. Group names only for now; domain-specific permissions come with
later slices.

### One-time development database reset

This slice introduces a custom user model (`AUTH_USER_MODEL = "accounts.User"`).
If your local Postgres volume already holds Django auth/admin tables from the
earlier scaffold, reset the development database volume **once** before
validating:

```powershell
docker compose down -v
```

This is safe only because no real data exists yet. It is a one-time transition
step, not a routine startup command.
