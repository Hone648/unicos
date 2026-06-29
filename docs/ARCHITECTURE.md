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
- The app is not production-ready yet.
- Production deployment is not implemented in the current slices. When it
  happens it will require secure settings, HTTPS, proper `ALLOWED_HOSTS`,
  `DEBUG=False`, secure cookies/CSRF/proxy headers, backups and restore
  procedure, admin hardening, media/document storage strategy, and
  deployment-specific environment management. See
  `DECISIONS/0006-web-capable-deployment.md`.
- The current Dockerfile uses Django `runserver`.
- Migrations currently run on container startup.
- Local Docker Compose is for development.
- Production settings are not split/hardened yet.
- HTTPS/proxy/security settings are not configured for deployment.
- Backups/restore are not specified.
- Admin hardening is incomplete.
- Media storage for attachments/photos/documents is not designed yet.

Authorization gap:

- The custom user model exists.
- Role groups exist as names/baseline groups.
- Most shop-facing views are login-gated.
- Domain-specific permission enforcement is not implemented yet.
- Any authenticated staff user may currently have too much functional access
  unless restricted outside the app.

Proposed permission matrix:

| Role | Intended access direction |
| --- | --- |
| Owner/Admin | All actions |
| Manager | Most operational actions, reports, and explicitly allowed workflow overrides |
| Front Desk | Customer intake, vehicle intake, repair-order intake, and possibly payments |
| Estimator | Estimates, supplements, repair-order notes, and status updates |
| Technician | View assigned ROs and update production notes/status where allowed |
| Read-only | View-only access |

The next implementation work should define and enforce permissions before
significantly expanding features.

Lifecycle-rule centralization gap:

- Some lifecycle rules are centralized, but not all entry points necessarily use
  the same service boundary.
- Shop-facing status changes block final repair-order statuses when a non-void
  invoice has balance due.
- That rule exists in `repair_orders/business_rules.py`.
- Admin bulk status actions call `ro.set_status()` directly.
- If admin is an intentional privileged override, this should be documented as
  such.
- If the rule is a true business invariant, it should move behind a domain
  service used by both views and admin.

Future service-layer direction:

```text
transition_repair_order_status(ro, new_status, actor, note, source)
issue_invoice(invoice, actor)
void_invoice(invoice, actor)
record_payment(invoice, data, actor)
edit_invoice_line_item(...)
```

Future domain spine:

```text
Customer -> Vehicle -> Repair Order -> Status -> Invoice -> Invoice Line Item -> Payment
```

Customer, Vehicle, Repair Order (with status history), Invoice, InvoiceLineItem,
and Payment now exist. Estimates and payment processor integration are planned
for later slices.

Missing body-shop workflow areas:

| Area | Missing examples |
| --- | --- |
| Estimating | estimates, supplements, estimate approval, estimate versions |
| Insurance | insurer, claim number, adjuster, deductible, DRP fields |
| Repair planning | labor operations, parts orders, sublet vendors, supplements |
| Customer communication | call/text/email log, authorization history |
| Attachments | photos, PDFs, signed forms, invoices, intake images |
| Scheduling | promised date exists, but not production calendar / technician scheduling |
| Shop operations | parts received, teardown, quality checklist, delivery checklist |
| Reporting | revenue, receivables, cycle time, open ROs, aging invoices |

List scalability gap:

Current list views are acceptable for early development, but larger datasets
need pagination and query hardening. Likely targets are the repair-order list,
customer list, invoice list, future payment list, and vehicle-related lists.
Future work should include pagination, stable ordering, select_related /
prefetch_related review, index review where needed, and search query safety.

Validation gap:

Current strengths include VIN normalization/validation, repair-order
customer/vehicle relationship validation, invoice/payment amount validation,
invoice due-date validation, and billing/final-status workflow guards.

Future improvements include phone formatting/normalization, state normalization,
optional uniqueness policies, VIN check-digit validation, realistic vehicle year
bounds, audit fields for customers/vehicles if needed, and clearer model/service
level enforcement for operations currently relying on views/forms.

Quality gate gap:

CI currently runs Django checks, missing migration checks, migrations, tests,
Docker build/runtime smoke, and `/healthz/`. Missing quality gates include Ruff
or equivalent linting, Black formatting, mypy/type checking, coverage reporting
and optional threshold, and pre-commit. These are useful next quality layers as
the app grows, but they are less urgent than permissions and lifecycle-rule
centralization.
