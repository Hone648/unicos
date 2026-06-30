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
- Custom user model (`accounts.User`) for staff authentication and centralized
  shop-facing app permission helpers in `accounts.authorization`
- Browser-based access
- Current operational interfaces:
  - Django admin: emergency/development back-office console for trusted
    superusers/staff; not the primary shop-facing workflow
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
  - Estimates: estimate create/detail/edit entered from repair-order detail
    (`/repair-orders/<pk>/estimates/new/`, `/estimates/<pk>/`,
    `/estimates/<pk>/edit/`); browser-printable estimate output
    (`/estimates/<pk>/print/`); explicit estimate status actions
    (`/estimates/<pk>/status/`); estimate line-item create/edit/delete
    (`/estimates/<pk>/line-items/new/`, `/estimates/line-items/<pk>/edit/`,
    `/estimates/line-items/<pk>/delete/`) and supplement create
    (`/estimates/<pk>/supplements/new/`); estimate detail shows line items,
    calculated total, and supplement lineage; an approved, itemized estimate can
    be converted into a draft invoice via
    `POST /estimates/<pk>/convert-to-invoice/` (requires `billing.manage`),
    copying estimate line items into invoice line items and linking the invoice
    back to its source estimate; estimate summary embedded in repair-order
    detail; estimates reuse repair-order permissions; no global estimate queue
    yet
  - Dashboard (`/`): read-only workflow overview for active repair orders,
    ready-for-pickup work, unpaid invoices, closure blockers, and recently
    updated repair orders
  - Reports (`/reports/`): read-only server-rendered operational snapshot built
    from existing repair-order, billing, and estimate models. It is gated by
    the explicit `reports.view` app permission and currently exposes aggregate
    counts plus limited attention queues; exports, date ranges, charts, and
    per-object report scoping are future work
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
  lifecycle transitions (draft -> issued, any -> void) are POST-only
  shop-facing actions at `/billing/invoices/<pk>/issue/` and
  `/billing/invoices/<pk>/void/`, backed by
  `billing.services.issue_invoice()` and `billing.services.void_invoice()`;
  void invoices are billing-read-only — invoice edit, line-item create/edit,
  and payment create are all blocked with a redirect and error message; invoices
  that belong to final repair orders are also billing-read-only in shop-facing
  mutation views; an optional nullable `source_estimate` FK (`PROTECT`,
  `related_name="converted_invoices"`, partial-unique while non-null) records the
  approved estimate an invoice was converted from — null for manually created
  invoices
- `billing.InvoiceLineItem`: itemized billing row linked to an invoice; supports
  labor, parts, materials, sublet, and misc rows; recalculates invoice subtotal
  on save
- `billing.Payment`: individual payment linked to an invoice; updates invoice
  payment status automatically on save/delete
- `estimates.Estimate`: estimate / insurance-claim context attached to a repair
  order; FK to repair order uses `PROTECT`; a repair order may have multiple
  estimates; tracks a small status lifecycle (draft/submitted/approved/declined/
  expired) plus insurance company, claim number, deductible, and estimated
  total; approved estimates capture approval source, contact, optional
  reference/note, and server-set approval timestamp; number is system-generated
  (`EST-YYYY-NNNNNN`); status changes are controlled by explicit shop-facing
  POST actions (`draft -> submitted`, `submitted -> approved/declined/expired`),
  and submitted/final estimates are read-only for normal estimate/detail and
  line-item mutation views; estimate-to-invoice conversion requires approval
  capture. An estimate may be an initial estimate or a supplement
  (`kind="supplement"`) that links back to a `parent_estimate` (`PROTECT`,
  self-FK) belonging to the same repair order; lineage rules are enforced in
  `Estimate.clean()`
- `estimates.EstimateLineItem`: itemized estimate row linked to an estimate via
  `CASCADE`; supports labor/parts/materials/sublet/misc rows; `save()` and
  `delete()` recalculate the parent estimate's `estimated_total`. Once an
  estimate has line items, `estimated_total` is calculated from them and the
  form disables manual editing (mirrors the billing invoice subtotal pattern);
  estimates with no line items keep a manual `estimated_total`. Estimate line
  items are separate from `billing.InvoiceLineItem` and do not feed invoices
- `attachments.Attachment`: a file attached to a repair order; stored under
  `MEDIA_ROOT/repair_orders/<ro_id>/<uuid>_<safe_basename>`; `original_filename`
  preserves the user-supplied name; `category` (photo/estimate/invoice/authorization/other),
  `description`, `size_bytes`, and `uploaded_by` are recorded at upload time; access is
  gated by the repair-order object policy (`can_view_repair_order` for download,
  `can_upload_attachment_for_repair_order` for upload, `can_delete_attachment` for delete);
  local `FileField` storage only — production storage/serving/scanning/backup is future work
- `core.DocumentNumberSequence`: tracks the last-used sequence value per
  `(document_type, year)` pair; powers the race-safe `RO-YYYY-NNNNNN`,
  `INV-YYYY-NNNNNN`, and `EST-YYYY-NNNNNN` generators in
  `core/document_numbers.py`

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
- Admin hardening is incomplete. Django admin is currently an
  emergency/development console, not a production operator workflow.
- Media storage for attachments/photos/documents is not designed yet.

Authorization:

- The custom user model exists.
- Baseline role groups exist: Owner/Admin, Manager, Front Desk, Estimator,
  Technician, and Read-only.
- `accounts.authorization` maps those role groups to explicit app-level
  permissions.
- Major shop-facing views require app permissions, not only login.
- `accounts.policies` adds object-level policy checks for repair-order,
  estimate, and billing views. App-level decorators remain the first gate.
- Reporting currently uses report-level authorization only via `reports.view`;
  per-object reporting scope and filtered exports are future work.
- Superusers and Owner/Admin retain full app-level access.
- `is_staff` is not treated as a shop permission.
- Templates may hide actions, but view checks are authoritative.
- Django admin still uses Django admin/staff/superuser authorization and is not
  unified with the shop-facing helper yet.

Current permission matrix:

| Role | Intended access direction |
| --- | --- |
| Owner/Admin | All actions |
| Manager | Most operational actions, reports, and explicitly allowed workflow overrides |
| Front Desk | Customer intake, vehicle intake, repair-order intake, and possibly payments |
| Estimator | Estimates, supplements, repair-order notes, and status updates |
| Technician | View assigned ROs and update production notes/status where allowed |
| Read-only | View-only access |

Remaining limitations:

- Technician access is intentionally conservative: technicians can view assigned
  repair orders in shop-facing repair-order views but cannot view unrelated
  repair orders, edit repair orders, change statuses, manage estimates, or
  mutate billing.
- Estimate and invoice object policies inherit repair-order object scope.
- Full customer/vehicle object policies are not implemented yet.
- Admin permissions are not unified with shop-facing helpers.

Admin policy:

- Django admin is an emergency/development back-office console for trusted
  superusers/staff.
- Shop-facing views are the authoritative operator workflow.
- Admin may expose fields and mutation paths hidden by the shop-facing UI.
- Services own lifecycle/business-state rules where implemented.
- Admin service alignment is partial: repair-order admin status saves/actions
  route through repair-order lifecycle services, while billing and estimate admin
  still save directly in places.
- Future production admin bypasses must either call the same domain services as
  shop-facing workflows or record an explicit override reason/audit trail.
- Full admin object-policy integration is future work. See
  `DECISIONS/0042-django-admin-policy.md`.

Lifecycle service layer:

- Repair-order status transitions are centralized in `repair_orders/services.py`
  via `transition_repair_order_status()`.
- `RepairOrder.set_status()` delegates to the service and is the normal public
  entry point.
- `RepairOrder._apply_status_change()` is a private low-level method for test
  setup only; application code must not call it.
- The unpaid-invoice final-status block is enforced by the service for all
  callers: shop-facing views, admin bulk actions, and admin status form saves.
- No admin override pathway exists; a future override slice would require
  explicit audit semantics.
- Estimate-to-invoice draft conversion is centralized in `billing/services.py`
  via `convert_estimate_to_invoice()` (with the
  `estimate_can_convert_to_invoice()` predicate). It validates that the estimate
  is approved, itemized, and not already converted, then creates a draft invoice
  and copies line items inside a single transaction.
- Billing workflow mutations are centralized in `billing/services.py`:
  `issue_invoice()`, `void_invoice()`, `record_payment()`,
  `create_invoice_line_item()`, and `edit_invoice_line_item()`. The service
  layer owns final-repair-order blocks, void-invoice blocks, invoice lifecycle
  state checks, line-item total checks, payment amount checks, overpayment
  checks, and payment status synchronization. Payment recording locks the
  invoice row with `select_for_update()` inside a transaction.

Future service-layer direction:

```text
create_invoice(...)
edit_invoice(...)
convert_or_merge_supplement_to_invoice(...)
```

List pagination:

- Major list pages use `core.pagination.paginate_queryset()` which wraps
  Django's built-in `Paginator.get_page()`.
- Page size is fixed at 25 (`DEFAULT_PAGE_SIZE`).
- Invalid and out-of-range `page` values are clamped silently.
- `core.pagination.pagination_querystring()` strips `page` from the query
  string so pagination links preserve existing filters without duplication.
- A shared template partial (`app/templates/partials/_pagination.html`) renders
  prev/page-indicator/next controls only when more than one page exists.
- No sortable columns, no user-configurable page size, no advanced search.

Future domain spine:

```text
Customer -> Vehicle -> Repair Order -> Status -> Invoice -> Invoice Line Item -> Payment
```

Customer, Vehicle, Repair Order (with status history), Invoice, InvoiceLineItem,
and Payment now exist. The Estimate spine now includes itemized estimate line
items (which drive the estimated total) and a minimal supplement lineage
(supplements are estimates with `kind="supplement"` and a parent estimate). An
approved, itemized estimate can be converted into a draft invoice
(`billing.services.convert_estimate_to_invoice`), copying estimate line items
into invoice line items and linking the invoice to its source estimate.
Generated PDF output, re-sync of estimate edits into an existing invoice,
supplement-to-invoice handling, and payment processor integration are planned for
later slices. Repair-order file attachments (photos, documents, signed forms) are
implemented via the `attachments` app using local `FileField` storage.

Media / attachments:

- `MEDIA_URL = "media/"`, `MEDIA_ROOT = REPO_ROOT / "media"` configured in settings.
- Django serves media files in `DEBUG` mode only (development-only `static()` handler).
- Production media serving (nginx, S3, presigned URLs) is future work.
- `media/` is in `.gitignore` and `.dockerignore`; files do not survive container
  recreation without a named volume or bind mount.
- `attachments.Attachment` upload path: `repair_orders/<ro_id>/<uuid>_<safe_basename>`.
- Access gated by existing repair-order object policies (no new permission primitives).

Missing body-shop workflow areas:

| Area | Missing examples |
| --- | --- |
| Estimating | estimate records, estimate line items, supplement lineage, browser-printable estimate output, a small approval status flow, approval capture, and approved-estimate-to-draft-invoice conversion exist; still missing full estimate versioning, generated PDF output, and supplement-to-invoice handling |
| Insurance | insurer, claim number, and deductible captured on estimates; still missing adjuster, DRP fields, coverage lines |
| Repair planning | labor operations, parts orders, sublet vendors, supplements |
| Customer communication | call/text/email log, authorization history |
| Attachments | basic repair-order file upload/download/delete implemented (Slice 42); still missing estimate/invoice-specific attachments, global attachment queue, thumbnails, image processing, production media serving, malware scanning, signed-form workflow |
| Scheduling | promised date exists, but not production calendar / technician scheduling |
| Shop operations | parts received, teardown, quality checklist, delivery checklist |
| Reporting | read-only operational snapshot exists for key repair-order, invoice, and estimate counts; still missing scoped filters, date ranges, exports, charts, revenue, receivables, cycle time, and aging invoices |

List scalability gap:

Current list views are acceptable for early development, but larger datasets
need pagination and query hardening. Likely targets are the repair-order list,
customer list, invoice list, future payment list, and vehicle-related lists.
Future work should include pagination, stable ordering, select_related /
prefetch_related review, index review where needed, and search query safety.

Form validation:

- Customer name validation: `Customer.clean()` enforces individual (first or
  last name required) and business (business_name required) name rules with
  `.strip()` checks; `CustomerForm` delegates via `ModelForm._post_clean()`.
- Vehicle VIN: normalized (strip + uppercase) by `Vehicle.clean_fields()`;
  validated by `validate_vin()` (17-char, no I/O/Q).
- Vehicle year: `VehicleForm.clean_year()` rejects values outside
  1900–(current year + 2) with a field-attached error message.
- Repair order customer/vehicle relationship: `RepairOrder.clean()` validates
  that the vehicle belongs to the selected customer.
- Invoice: `Invoice.clean()` enforces subtotal/tax ≥ 0 and due_date ≥ issued_at.
- Invoice line items: `InvoiceLineItemForm.clean_quantity()` rejects quantity ≤ 0;
  `clean_unit_price()` rejects negative prices; both attach errors to their
  respective fields.
- Payment: `PaymentForm.clean_amount()` rejects amount ≤ 0 at field level;
  `Payment.clean()` additionally checks for overpayment and void-invoice
  rejection after the view sets the invoice FK.

Remaining validation gaps: phone formatting, state normalization, VIN
check-digit validation, optional uniqueness policies.

Quality gates:

CI currently runs Ruff lint/format checks, Django checks, missing migration
checks, migrations, tests, Docker build/runtime smoke, and `/healthz/`. Ruff is
the first Python quality gate and is used for both linting and formatting.
Development-only tooling lives in `requirements-dev.txt`, with local pre-commit
hooks configured in `.pre-commit-config.yaml`.

Deferred quality layers include mypy/Django typing evaluation, coverage
reporting without an initial threshold, and broader Ruff rules after the baseline
stabilizes. Black is intentionally not used so Ruff remains the only formatter.
