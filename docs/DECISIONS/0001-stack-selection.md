# 0001: Stack Selection

Status: Accepted

Decision:

Use Django, PostgreSQL, HTMX, Tailwind, and Docker Compose.

Rationale:

- Django gives the project a mature server-rendered web framework with admin,
  migrations, forms, auth, and strong relational modeling.
- PostgreSQL supports realistic multi-user shop usage and durable relational
  data.
- HTMX can add interaction later without forcing a full SPA architecture.
- Tailwind can support a practical custom UI when the project reaches that
  slice.
- Docker Compose provides repeatable local app and database runtime.

Rejected alternatives:

- Next.js/React-first: rejected for MVP complexity.
- Microservices: rejected as overkill for the initial product.
- SQLite: rejected for multi-user real use.
