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
  - Django admin: full back-office operations for customer, vehicle, repair
    order, and billing records
  - Repair-order workspace (`/repair-orders/`): shop-facing list, detail,
    create, and edit views; staff can search, filter, view, create, edit, and
    change repair order status without using Django admin
  - Customer workspace (`/customers/`): shop-facing customer list, detail,
    create, and edit views; vehicle create-for-customer, detail, and edit under
    `/customers/<pk>/vehicles/new/` and `/vehicles/<pk>/`
  - Billing workspace (`/billing/`): invoice create-for-repair-order, invoice
    queue/list, invoice edit, invoice detail/print view, invoice line-item
    create/edit, and payment create; invoice summary with line items and
    payments embedded in repair-order detail
  - Dashboard (`/`): read-only workflow overview for active repair orders,
    ready-for-pickup work, unpaid invoices, closure blockers, and recently
    updated repair orders
- UI styling: plain Django static CSS (`app/static/css/unicos.css`); no
  frontend build tooling, no Tailwind
- HTMX: loaded via CDN script tag (pinned 2.0.4, defer); used only for the
  repair-order status update form; normal POST/redirect fallback preserved

Current domain models:

- `customers.Customer`: individual or business customer; one-to-many with
  vehicles
- `vehicles.Vehicle`: VIN-keyed vehicle belonging to one customer; FK uses
  `PROTECT` to preserve history
- `repair_orders.RepairOrder`: central shop workflow record linking customer,
  vehicle, and assigned staff; status is a controlled `TextChoices` enum (not a
  configurable DB table); FKs to customer and vehicle use `PROTECT`; number is
  system-generated (`RO-YYYY-NNNNNN`) — staff do not type it manually;
  final-status transitions (delivered, closed, canceled) are blocked by the
  shop-facing status-update view when a non-void invoice has a balance due;
  ordinary repair-order field edits and shop-facing billing mutations are
  blocked once the order is delivered, closed, or canceled, while detail,
  history, billing summary, printable invoices, and allowed status movement
  remain visible/available
- `repair_orders.RepairOrderStatusHistory`: append-only audit trail of status
  changes on a repair order; cascades with the repair order
- `billing.Invoice`: one-to-one with RepairOrder; tracks subtotal, tax, and
  payment status (draft/issued/partially paid/paid/void); subtotal is manual
  until line items exist, then calculated from line items; number is
  system-generated (`INV-YYYY-NNNNNN`) — staff do not type it manually;
  lifecycle transitions (draft→issued, any→void) are POST-only shop-facing
  actions at `/billing/invoices/<pk>/issue/` and `/billing/invoices/<pk>/void/`;
  void invoices are billing-read-only — invoice edit, line-item create/edit,
  and payment create are all blocked with a redirect and error message; invoices
  that belong to final repair orders are also billing-read-only in shop-facing
  mutation views
- `billing.InvoiceLineItem`: itemized billing row linked to an invoice; supports
  labor, parts, materials, sublet, and misc rows; recalculates invoice subtotal
  on save
- `billing.Payment`: individual payment linked to an invoice; updates invoice
  payment status automatically on save/delete
- `core.DocumentNumberSequence`: tracks the last-used sequence value per
  `(document_type, year)` pair; powers the race-safe `RO-YYYY-NNNNNN` and
  `INV-YYYY-NNNNNN` generators in `core/document_numbers.py`

Status is currently implemented as `RepairOrder.Status` (TextChoices enum). No
configurable status table exists yet.

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
Customer -> Vehicle -> Repair Order -> Status -> Invoice -> Invoice Line Item -> Payment
```

Customer, Vehicle, Repair Order (with status history), Invoice, InvoiceLineItem,
and Payment now exist. Estimates and payment processor integration are planned
for later slices.
