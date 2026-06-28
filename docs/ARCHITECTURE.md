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
- Current operational interfaces:
  - Django admin: full back-office operations (customer, vehicle, repair order, billing)
  - Repair-order workspace (`/repair-orders/`): shop-facing list, detail, create, and
    edit views; staff can search, filter, view, create, edit, and change repair order
    status without using Django admin
- UI styling: plain Django static CSS (`app/static/css/unicos.css`); no frontend
  build tooling, no Tailwind
- HTMX: loaded via CDN script tag (pinned 2.0.4, defer); used only for the
  repair-order status update form; normal POST/redirect fallback preserved

Current domain models:

- `customers.Customer` — individual or business customer; one-to-many with vehicles
- `vehicles.Vehicle` — VIN-keyed vehicle belonging to one customer; FK uses `PROTECT` to preserve history
- `repair_orders.RepairOrder` — central shop workflow record linking customer, vehicle, and assigned staff; status is a controlled `TextChoices` enum (not a configurable DB table); FKs to customer and vehicle use `PROTECT`
- `repair_orders.RepairOrderStatusHistory` — append-only audit trail of status changes on a repair order; cascades with the repair order
- `billing.Invoice` — one-to-one with RepairOrder; tracks subtotal, tax, and payment status (draft/issued/partially paid/paid/void); invoice totals are manual fields until line items exist
- `billing.Payment` — individual payment linked to an invoice; updates invoice payment status automatically on save/delete

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

Customer, Vehicle, Repair Order (with status history), Invoice, and Payment now exist.
Line items, estimates, and payment processor integration are planned for later slices.
