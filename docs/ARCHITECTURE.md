# Architecture

Approved stack:

- Django
- PostgreSQL
- HTMX later
- Tailwind later
- Docker Compose

Architectural style:

- Server-rendered Django monolith
- PostgreSQL relational database
- Local-network-first deployment
- Browser-based access

Future domain spine:

```text
Customer -> Vehicle -> Repair Order -> Status -> Invoice -> Payment
```

This spine is directional planning only. Slice 1 does not define these domain
models.
