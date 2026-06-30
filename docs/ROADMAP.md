# Roadmap

This roadmap reflects the current implementation after Slice 40. It should guide
slice planning but can change after implementation review and user feedback.

## Current State

Implemented:

- Django/PostgreSQL/Docker Compose scaffold
- Custom user model, login/logout, and baseline role groups
- Initial app-level permission helpers, role-based shop-facing view
  enforcement, and an object-level policy scaffold
- Explicit Django admin policy decision: admin is an emergency/development
  back-office console, not the primary shop-facing workflow
- Customer and vehicle records
- Repair orders, status history, create/edit workflow, and HTMX status updates
- Dashboard workflow visibility
- Billing foundation, invoices, payments, invoice line items, printable invoice
  detail, lifecycle actions, invoice queue, and a service boundary for billing
  mutations
- Estimate and insurance spine, estimate line items, supplement lineage,
  browser-printable estimate output, controlled approval status actions, and
  approval capture for approved estimates
- Generated repair-order and invoice numbers
- Guards for void invoices, final repair-order edits, final repair-order billing
  mutations, and unpaid-invoice closure blocking
- CI with Ruff lint/format checks, Django checks, missing migration checks,
  migrations, full tests, Docker build/runtime smoke, and `/healthz/`

The app is local-development only and is not production-ready.

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

Proposed matrix:

| Role | Intended access direction |
| --- | --- |
| Owner/Admin | All actions |
| Manager | Most operational actions, reports, and explicitly allowed workflow overrides |
| Front Desk | Customer intake, vehicle intake, repair-order intake, and possibly payments |
| Estimator | Estimates, supplements, repair-order notes, and status updates |
| Technician | View assigned ROs and update production notes/status where allowed |
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

Status: partially implemented in Slices 26, 37, and 39.

```text
Slice 26: repair-order lifecycle service boundary
Slice 37: billing service boundary and payment concurrency guarantee
Slice 39: Django admin policy decision / ADR
```

Repair-order status transitions are now centralized in
`repair_orders/services.py`. The unpaid-invoice final-status block is enforced
uniformly across shop-facing views and Django admin.

Billing mutations are now centralized in `billing/services.py` for invoice
issue, invoice void, payment recording, and invoice line-item create/edit.
Payment recording locks the invoice row with `select_for_update()` before
checking balance and saving the payment.

Remaining service-layer gaps:

- No admin override pathway exists for lifecycle rules.
- Admin service alignment is partial: repair-order admin status changes route
  through services, while billing and estimate admin still save directly in
  places.

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

Track now, implement later.

Required later:

- Replace Django `runserver`.
- Split development and production Compose/deployment configuration.
- Harden secure settings.
- Configure HTTPS/proxy headers.
- Configure secure cookies and HSTS.
- Document backups and restore.
- Lock down admin access.
- Align admin mutations with domain services or require explicit audited
  override reasons for production bypasses.
- Design media storage for attachments/photos/documents.
- Define deployment-specific environment management.

Recommended next slices:

- Reporting foundation.
- Attachments/media model.
- Admin service-alignment and override audit later.

## Missing Body-Shop Workflow Areas

| Area | Missing examples |
| --- | --- |
| Estimating | estimates, supplements, browser-printable estimate output, controlled estimate approval status, approval capture, estimate versions |
| Insurance | insurer, claim number, adjuster, deductible, DRP fields |
| Repair planning | labor operations, parts orders, sublet vendors, supplements |
| Customer communication | call/text/email log, authorization history |
| Attachments | photos, PDFs, signed forms, invoices, intake images |
| Scheduling | promised date exists, but not production calendar / technician scheduling |
| Shop operations | parts received, teardown, quality checklist, delivery checklist |
| Reporting | revenue, receivables, cycle time, open ROs, aging invoices |

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
