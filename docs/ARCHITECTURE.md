# Architecture

Approved stack (unchanged):

- Django
- PostgreSQL
- HTMX later
- Tailwind later
- Docker Compose

Architectural style:

- Server-rendered Django monolith
- PostgreSQL relational database
- Custom user model (`accounts.User`) for staff authentication
- Browser-based access

Deployment:

- Development now runs on local Docker Compose (app + PostgreSQL).
- The intended shop has internet access, so a web-capable / hosted deployment
  path is expected later.
- Production deployment is not implemented in the current slices. When it
  happens it will require secure settings, HTTPS, proper `ALLOWED_HOSTS`,
  backups, admin hardening, and general security hardening. See
  `DECISIONS/0006-web-capable-deployment.md`.

Future domain spine:

```text
Customer -> Vehicle -> Repair Order -> Status -> Invoice -> Payment
```

This spine is directional planning only. The current slices do not define these
domain models.
