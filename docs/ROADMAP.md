# Roadmap

This roadmap reflects Slices 48–49 and the merged repair-order follow-ups
through PR #64. Slice planning can change after implementation review and
user feedback.

## Current State

Implemented:

- Django/PostgreSQL/Docker Compose scaffold
- Custom user model, login/logout, and baseline role groups
- Initial app-level permission helpers, role-based shop-facing view
  enforcement, and an object-level policy scaffold
- Explicit Django admin policy decision: admin is an emergency/development
  back-office console, not the primary shop-facing workflow
- Customer and vehicle records
- Repair-order create/edit workflow and a detail page grouped by overview,
  next action, estimate and invoice, and activity and files
- Shared repair-order status rules for shop views and Django admin, auditable
  cancel/reopen actions, Closed date display, and HTMX status updates
- New repair orders can start from the list, a customer, or an active vehicle.
  The form scopes vehicle choice to the selected customer and uses HTMX to
  refresh the options. The intake update adds responsive forms and vehicle
  comparison for similar vehicles.
- Repair-order communication log for customer/insurer/adjuster/internal history
- Bootstrap-based UI foundation using local static assets, a Bootstrap navbar,
  Bootstrap alerts/buttons/cards/tables on high-traffic pages, and the existing
  `unicos.css` file as the domain-specific override layer
- Dashboard workflow visibility
- Billing foundation, invoices, payments, invoice line items, printable invoice
  detail, lifecycle actions, invoice queue, and a service boundary for billing
  mutations
- Estimate and insurance spine, estimate line items, supplement lineage,
  browser-printable estimate output, controlled approval status actions, and
  approval capture, and approved-estimate-to-draft-invoice conversion
- Estimate and invoice tax totals, with historical amounts preserved through
  the tax migration and review for unverified draft tax breakdowns
- Generated repair-order and invoice numbers
- Guards for void invoices, final repair-order edits, final repair-order billing
  mutations, and unpaid-invoice closure blocking. The balance warning offers
  eligible staff a payment shortcut back to the pending status action.
- CI with Ruff lint/format checks, Django checks, missing migration checks,
  migrations, full tests, Docker build/runtime smoke, and `/healthz/`
- Read-only reporting at `/reports/` for repair-order, billing, and estimate
  operational snapshots, with date/status filters and CSV exports gated by
  `reports.view`
- Repair-order file attachments (upload, download, delete; local `media/`
  storage; policy-gated)
- Attachment hardening and local Docker media persistence (`media_data` volume,
  health check coverage, filename/content validation, and missing-file
  download/delete behavior)
- Admin service alignment: estimate status changes, invoice issue/void,
  payment recording, and invoice line-item mutation in Django admin are
  service-backed or read-only, matching the existing repair-order admin
  pattern

The current runnable setup is for local development. The single-shop LAN
beta is planned. Internet-hosted production remains a future goal.

Product Slice 46 is now consumed by the repair-order communication log.
Product Slice 47 is now consumed by the Bootstrap UI foundation.

## Priority Roadmap

### Priority 1 - README / Docs Reality Check

Status: implemented in Slices 24 and 35.

Keep the README, architecture docs, roadmap, and ADRs aligned with the real
state of the app. The docs should distinguish implemented features from
readiness gaps and future direction. Slice 35 added a user-facing operator
manual (`docs/USER_MANUAL.md`) covering the full implemented workflow.

### Priority 2 - Real Role/Permission Enforcement

Status: implemented in Slice 25 at an initial app-permission level and extended
with object-level policy scaffolding in Slice 38.

```text
Slice 25: authorization matrix and permission helpers
Slice 38: object-level authorization policy scaffold
```

The app now defines a domain-specific permission matrix and enforces app-level
permissions in major shop-facing views. `accounts.policies` adds object-level
policy checks for repair orders, estimates, and billing objects.

Current shop-facing roles:

| Role | Access relevant to repair orders |
| --- | --- |
| Owner/Admin | All actions |
| Manager | Shop workflow, reports, and reason-required cancel and reopen actions |
| Front Desk | Customer, vehicle, and repair-order intake, estimate work, invoice viewing, and payment recording |
| Estimator | View repair orders, estimates, and invoices and make routine repair-order status changes |
| Technician | View assigned repair orders |
| Read-only | View-only access |

Remaining limits:

- Technician repair-order access is scoped to assigned repair orders in
  shop-facing repair-order views.
- Estimate and invoice policies inherit repair-order object scope.
- Django admin still uses Django admin/staff/superuser authorization and is not
  unified with shop-facing helpers.
- `is_staff` is not treated as a shop permission.
- Templates hide obvious actions where practical, but view checks remain
  authoritative.

### Priority 3 - Centralized Lifecycle/Domain Services

Status: implemented in Slices 26, 37, 39, and 43.

```text
Slice 26: repair-order lifecycle service boundary
Slice 37: billing service boundary and payment concurrency guarantee
Slice 39: Django admin policy decision / ADR
Slice 43: admin service-alignment / override audit
```

Shop-facing views and Django admin share the repair-order transition policy
and lifecycle service. The service validates the saved status, enforces the
invoice balance guard, and records the actor and reason for cancel and reopen
actions.

Billing mutations are now centralized in `billing/services.py` for invoice
issue, invoice void, payment recording, and invoice line-item create/edit.
Payment recording locks the repair order first and the invoice second before
checking the balance or saving. A payment shortcut also rechecks the pending
action and permissions under those locks.

Slice 43 aligned admin estimate status changes, invoice issue and void,
payment recording, and invoice line-item mutation with their respective
services or made the fields read-only. See
`DECISIONS/0046-admin-service-alignment.md`.

Slice-numbering note: the actual Git-backed sequence is canonical. The
originally planned separate "billing views call services only" slice was
absorbed into actual Slice 37 because billing services now own invoice
issue/void, payment recording, and invoice line-item mutations while views call
services. Actual Slice 43 was inserted as an admin service-alignment hardening
slice. The post-Slice-43 customer-scoped vehicle-dropdown UX fix is unnumbered.
Slice 44 then added reporting filters/date ranges and CSV export.

Remaining service-layer gaps:

- No admin override pathway exists for lifecycle rules; a blocked admin
  action simply fails with an error message rather than offering an audited
  override.
- Full admin object-level permission integration (matching the shop-facing
  policy layer) is not implemented; admin authorization is still Django's
  own staff/superuser model.

Future service-layer direction:

```text
create_invoice(...)
edit_invoice(...)
convert_or_merge_supplement_to_invoice(...)
```

### Priority 4 - Pagination And Query Safety

Status: implemented in Slice 27.

```text
Slice 27: list pagination and query safety
```

Major list pages now use Django's built-in paginator with a fixed page size of
25. Invalid and out-of-range page values are clamped safely. Query parameters
(search, status filters) are preserved across pagination links.

Remaining pagination gaps:

- No sortable columns.
- No user-configurable page size.
- No advanced search or full-text indexing.
- No database indexes added (acceptable for current dataset sizes).
- Future payment list and vehicle-related list pages if they are created.

### Priority 5 - Form Validation and Data Integrity Hardening

Status: implemented in Slice 28.

```text
Slice 28: form validation and data integrity hardening
```

Form-level clean methods were added for vehicle year range, invoice line-item
quantity and unit price, and payment amount. All produce field-attached error
messages rather than generic MinValueValidator text.

Remaining validation gaps: phone formatting, state normalization, VIN
check-digit validation, optional uniqueness policies.

### Priority 6 - Estimate/Insurance Spine

Status: partially implemented in Slices 29, 30, 32, 33, 34, and 36.

```text
Slice 29: estimate and insurance spine
Slice 30: estimate line items and supplements
Slice 32: printable estimate output
Slice 33: estimate approval status flow
Slice 34: estimate-to-invoice draft conversion
Slice 36: customer/insurer approval capture
```

The `Estimate` model lives in the `estimates` app, linked to `RepairOrder` via
`PROTECT`, allowing multiple estimates per repair order. It captures a small
status lifecycle (draft/submitted/approved/declined/expired), insurance company,
claim number, deductible, estimated total, and notes. Estimate numbers are
generated (`EST-YYYY-NNNNNN`). Slice 30 added `EstimateLineItem` (line items
that drive `estimated_total` once any exist; manual total preserved otherwise)
and a minimal supplement lineage (`kind="supplement"` + `parent_estimate`).
Slice 33 controls estimate status through explicit POST actions:
`draft -> submitted`, then `submitted -> approved/declined/expired`. Submitted
and terminal estimates are read-only for normal estimate edit and line-item
mutation views. Shop-facing create/detail/edit, browser-printable estimate
output, line-item create/edit/delete, status actions, and supplement create are
entered from repair-order detail and estimate detail. Estimates reuse
repair-order permissions. Slice 34 added a controlled conversion: an approved,
itemized estimate can be turned into a *draft* invoice via `billing.services`,
copying estimate line items into invoice line items and linking the invoice back
to its source estimate (`Invoice.source_estimate`, with duplicate conversion
blocked). Slice 36 added approval capture fields (source, contact, optional
reference/note, timestamp) and requires captured approval before an approved
estimate can be converted. Invoice issuing, voiding, and payment behavior are
unchanged.

Proposed remaining model direction:

```text
RepairOrder
  -> Estimate            (implemented: spine)
  -> EstimateLineItem    (implemented)
  -> Supplement          (implemented: Estimate kind=supplement + parent)
  -> Invoice draft       (implemented: approved estimate -> draft invoice)
  -> InsuranceClaim      (deferred: richer insurance modeling)
```

Remaining estimate gaps:

- Conversion is one-way (estimate -> draft invoice); no re-sync of estimate
  edits into an existing invoice and no "unconvert" action.
- No supplement-to-invoice handling or multi-estimate invoice merging (a repair
  order still has a single one-to-one invoice).
- No customer signatures, approval uploads, email approval links, or customer
  portal approval.
- No generated PDF estimate output.
- No full estimate versioning engine (supplements are a minimal lineage only).
- No estimate locking by repair-order final status (deferred).
- No global estimate queue / list page.

Do not jump to payment processor integration before insurance-claim modeling
and supplement-to-invoice handling are clearer.

### Priority 7 - Production Hardening

The [LAN-00 through LAN-14 plan](SLICE_PLAN.md#lan-beta-slices) tracks the
first controlled deployment. The approved topology uses one dedicated
Linux PC with Docker Compose and PostgreSQL. Shop browsers reach it on the
LAN only. Web serving, TLS and trust, secure settings and secrets, private
media and upload screening, administrative access, recovery, and release
controls remain open implementation work.

Record the host, operating system, network, and power
[prerequisites](SLICE_PLAN.md#lan-beta-deployment-prerequisites) in LAN-01.
Deployed network verification begins in LAN-03 after the controls are in
place.

Before shop use, verify the network boundary and restore procedure, confirm
the shop's tax configuration, and complete the synthetic workflow checks in
the [acceptance gates](SLICE_PLAN.md#lan-beta-acceptance-gates). One server and
an on-site NVMe copy leave both downtime and single-site data loss risk.

Internet-hosted production will need its own readiness review under
[ADR 0006](DECISIONS/0006-web-capable-deployment.md). Open work includes
hosted network exposure and trust, environment management, broader recovery
and availability, and any audited admin override pathway. The existing
development setup remains the path for local testing.

### Priority 8 - Reporting

Status: implemented in Slices 41 and 44.

```text
Slice 41: reporting foundation
Slice 44: reporting filters/date ranges and CSV export
```

Reports now provide a read-only `/reports/` operational snapshot behind
`reports.view`, with date/status filters and CSV exports for repair orders,
invoices, and estimates.

Remaining reporting gaps:

- Charts.
- Revenue reporting.
- Receivables and aging.
- Cycle-time reporting.
- Scoped reporting / object-level aggregate strategy.

### Priority 9 - Attachments / Media Foundation

Status: implemented in Slice 42 and hardened in Slice 45.

```text
Slice 42: repair-order attachments/media model
Slice 45: attachment hardening / media persistence
```

Repair orders can now have file attachments (photos, signed estimates, documents).
Upload, download, and delete are policy-gated. Files are stored under local
`media/` using Django `FileField`, and Docker Compose mounts `media_data` at
`/app/media` so local uploads survive container recreation. Media is served in
development only (`DEBUG=True`). Upload validation now checks filename
shape/length, extension allowlist, content-type alignment, size, and lightweight
binary signatures for image/PDF types. See
`DECISIONS/0047-local-media-persistence.md`.

Remaining attachment gaps:

- Estimate-specific, invoice-specific, or customer-level attachments not yet scoped.
- No global attachment queue or search.
- No image thumbnails or preview.
- Production media serving/storage/scanning/backup is future work.

### Priority 10 - Admin Service Alignment

Status: implemented in Slice 43.

```text
Slice 43: admin service-alignment / override audit
```

Django admin no longer silently bypasses domain services for high-risk
mutations. Estimate status changes (including approval capture), invoice
issue/void, payment recording, and invoice line-item create/edit are routed
through their respective service functions or made read-only in admin.
Attachment evidence/upload metadata is readonly after upload and delete is
disabled. See `DECISIONS/0046-admin-service-alignment.md`.

Remaining admin gaps:

- No audited override pathway for blocked admin actions — a blocked action
  simply fails with an error message.
- No admin object-level permission framework; admin authorization is still
  Django's own staff/superuser model, separate from the shop-facing policy
  layer.
- `EstimateAdmin` still allows direct editing of approval metadata text
  fields (source/contact/reference/note) outside of a status transition;
  only `approved_at` and the transition itself are service-controlled.

### Priority 11 - Communication History

Status: implemented in Slice 46.

```text
Slice 46: repair-order communication log
```

Repair orders now have a create-only communication log for customer, insurer,
adjuster, vendor, tow-provider, and internal communication notes. Entries record
when communication happened, direction/channel, contact role/name, summary,
optional next step/outcome, authorization relevance, and who logged it.

Remaining communication gaps:

- No structured customer/insurer/adjuster contact model.
- No customer-level or global communication list.
- No email/SMS sending or inbound sync.
- No reminders, follow-up tasks, portal, signatures, or uploads.

Workflow follow-up candidates:

- Clearer estimate action guidance and approval requirements.
- Payment-form usability, including keyboard entry and date and amount guidance.
- Supplement-to-invoice handling, repair planning for parts and sublet work,
  and structured customer and insurer contacts.

Production media storage, serving, scanning, and backups remain open under
[Production Hardening](#priority-7---production-hardening).

## Missing Body-Shop Workflow Areas

| Area | Missing examples |
| --- | --- |
| Estimating | Full estimate versioning, generated PDFs, and supplement-to-invoice handling |
| Insurance | Adjuster records, DRP fields, coverage lines, and richer claim tracking |
| Repair planning | Labor operations, parts orders, and sublet vendor tracking |
| Customer communication | repair-order communication log implemented; still missing structured contacts, global communication views, email/SMS integrations, reminders, portal, signatures, and uploads |
| Attachments | repair-order file upload/download/delete implemented with local Docker media persistence and lightweight validation hardening; still missing estimate/invoice-specific attachments, global queue, thumbnails, production media serving, malware scanning |
| Scheduling | promised date exists, but not production calendar / technician scheduling |
| Shop operations | parts received, teardown, quality checklist, delivery checklist |
| Reporting | read-only operational snapshot with date/status filters and CSV exports exists; still missing charts, revenue, receivables/aging, cycle time, and scoped object-level aggregate strategy |

## Validation Roadmap

Current strengths:

- VIN normalization and validation
- Repair-order customer/vehicle relationship validation
- Invoice/payment amount validation
- Invoice due-date validation
- Billing/final-status workflow guards

Future improvements:

- Phone formatting/normalization
- State normalization
- Optional uniqueness policies
- VIN check-digit validation
- Realistic vehicle year bounds
- Audit fields for customers/vehicles if needed
- Clearer model/service-level enforcement for operations currently relying on
  views/forms

## Quality Gate Roadmap

Current CI runs:

- Ruff lint and format checks
- Django checks
- Missing migration checks
- Migrations
- Tests
- Docker build/runtime smoke
- `/healthz/`

Missing quality gates:

- mypy/type checking
- Coverage reporting and optional threshold
- broader Ruff rules after the baseline stabilizes

Ruff is the first quality gate and handles both linting and formatting. Black,
mypy, and coverage thresholds remain deferred.
