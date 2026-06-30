# Unicos

Unicos is a web-based body shop repair order management app. It is currently a
local-development Django/PostgreSQL application that runs with Docker Compose.

## Current Deployment Status

Unicos is local development only and is not production-ready.

Production deployment still requires:

- Production web serving instead of Django `runserver`
- Secure settings
- HTTPS
- Correct `ALLOWED_HOSTS`
- `DEBUG=False`
- Secure cookies, CSRF, and proxy header configuration
- Backups and a restore procedure
- Admin hardening
- Media/document storage strategy
- Deployment-specific environment management

Screenshots are future work; the repo does not currently include a maintained
screenshot set.

## Current Features

- Custom user model and login/logout
- Initial role-based shop-facing permission enforcement
- Dashboard/workflow visibility
- Customers and vehicles
- Repair orders and status history
- Shop-facing repair-order workspace
- HTMX status updates
- Repair-order create/edit workflow
- Billing foundation
- Invoices and payments
- Invoice line items
- Printable invoice view
- Invoice lifecycle actions
- Void invoice edit guards
- Final repair-order edit guards
- Final repair-order billing guards
- Closure rule blocking final RO statuses when active invoice has balance due
- Generated document numbers
- Billing invoice queue
- Hardened CI with Ruff quality checks, migration checks, Docker smoke, and healthz

## Stack

- Django
- PostgreSQL
- Docker Compose
- GitHub Actions
- Plain server-rendered HTML/CSS with limited HTMX; no frontend build tooling

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

Create a superuser to sign in and reach the dashboard or Django admin:

```powershell
docker compose exec web python app/manage.py createsuperuser
```

Django admin is an emergency/development back-office console for trusted
superusers/staff. Normal operators should use the shop-facing app, not admin, and
admin should not be used as a routine production workflow.

## Default Validation Commands

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
docker compose build
docker compose up -d
docker compose exec web python app/manage.py check
docker compose exec web python app/manage.py makemigrations --check
docker compose exec web python app/manage.py migrate --noinput
docker compose exec web python app/manage.py test
Invoke-RestMethod http://localhost:8000/healthz/
docker compose down
```

For non-Docker local runs, install `requirements.txt` and provide the same
environment variables shown in `.env.example`.

## Development Quality Checks

Install development tooling:

```powershell
python -m pip install -r requirements-dev.txt
```

Run local quality checks:

```powershell
ruff check .
ruff format --check .
```

Format Python files when needed:

```powershell
ruff format .
```

Set up pre-commit hooks:

```powershell
pre-commit install
pre-commit run --all-files
```

## CI Validation

GitHub Actions runs a Ruff quality job, a PostgreSQL-backed Django test job, and
a separate Docker smoke job. CI checks Ruff linting/formatting, Django system
checks, missing migrations, migration application, the full test suite, Docker
image build, Docker Compose startup, and `/healthz/`.

## Authentication And Authorization

The app has a login/logout baseline backed by a custom user model
(`accounts.User`).

- `/` is an authenticated dashboard. Unauthenticated visitors are redirected to
  `/accounts/login/?next=/`.
- `/accounts/login/` and `/accounts/logout/` handle sign in and sign out.
- `/healthz/` remains public.

Baseline staff role groups (`Owner/Admin`, `Manager`, `Front Desk`,
`Estimator`, `Technician`, `Read-only`) are created automatically by a data
migration. Shop-facing views now use centralized app-level permission helpers
from `accounts.authorization`.

Current authorization limits:

- Object-level policies currently cover high-value repair-order, estimate, and
  billing views; full customer/vehicle object policies remain future work.
- Technician repair-order access is scoped to assigned repair orders in
  shop-facing views.
- `is_staff` is not treated as a shop permission.
- Django admin still uses Django admin authorization and is intentionally
  separate from shop-facing authorization policy.
- Admin service alignment is partial and remains future work.
- Production hardening remains future work.

## Roadmap And Readiness

See `docs/ROADMAP.md` for the current readiness roadmap and `docs/ARCHITECTURE.md`
for architectural context, current gaps, and future direction.

See [docs/USER_MANUAL.md](docs/USER_MANUAL.md) for the operator-facing workflow guide.
