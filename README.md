# Unicos

Unicos is a local-first body shop repair order management app. This slice only
sets up the Django, PostgreSQL, Docker, and CI foundation.

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

Run tests:

```powershell
docker compose exec web python app/manage.py test
```

For non-Docker local runs, install `requirements.txt` and provide the same
environment variables shown in `.env.example`.
