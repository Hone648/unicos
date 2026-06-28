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
- Current operational interface: Django admin, with improved workflows for
  customer lookup, vehicle lookup, repair order management, and status history
  review. Custom UI is planned for a later slice.

Current domain models:

- `customers.Customer` — individual or business customer; one-to-many with vehicles
- `vehicles.Vehicle` — VIN-keyed vehicle belonging to one customer; FK uses `PROTECT` to preserve history
- `repair_orders.RepairOrder` — central shop workflow record linking customer, vehicle, and assigned staff; status is a controlled `TextChoices` enum (not a configurable DB table); FKs to customer and vehicle use `PROTECT`
- `repair_orders.RepairOrderStatusHistory` — append-only audit trail of status changes on a repair order; cascades with the repair order

Status is currently implemented as `RepairOrder.Status` (TextChoices enum). No configurable status table exists yet.

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

Customer, Vehicle, and Repair Order (with status history) now exist. Invoice and
Payment are planned for later slices.
