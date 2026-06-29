# Roadmap

This roadmap reflects the current implementation after Slice 23. It should guide
slice planning but can change after implementation review and user feedback.

## Current State

Implemented:

- Django/PostgreSQL/Docker Compose scaffold
- Custom user model, login/logout, and baseline role groups
- Initial app-level permission helpers and role-based shop-facing view
  enforcement
- Customer and vehicle records
- Repair orders, status history, create/edit workflow, and HTMX status updates
- Dashboard workflow visibility
- Billing foundation, invoices, payments, invoice line items, printable invoice
  detail, lifecycle actions, and invoice queue
- Generated repair-order and invoice numbers
- Guards for void invoices, final repair-order edits, final repair-order billing
  mutations, and unpaid-invoice closure blocking
- CI with Django checks, missing migration checks, migrations, full tests,
  Docker build/runtime smoke, and `/healthz/`

The app is local-development only and is not production-ready.

## Priority Roadmap

### Priority 1 - README / Docs Reality Check

Status: this slice.

Keep the README, architecture docs, roadmap, and ADRs aligned with the real
state of the app. The docs should distinguish implemented features from
readiness gaps and future direction.

### Priority 2 - Real Role/Permission Enforcement

Status: implemented in Slice 25 at an initial app-permission level.

```text
Slice 25: authorization matrix and permission helpers
```

The app now defines a domain-specific permission matrix and enforces app-level
permissions in major shop-facing views.

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

- No object-level permissions yet.
- No technician assignment constraints yet.
- Django admin still uses Django admin/staff/superuser authorization and is not
  unified with shop-facing helpers.
- `is_staff` is not treated as a shop permission.
- Templates hide obvious actions where practical, but view checks remain
  authoritative.

### Priority 3 - Centralized Lifecycle/Domain Services

Likely future slice:

```text
Slice 26: repair-order/billing lifecycle service layer
```

Some lifecycle rules are centralized, but not all entry points necessarily use
the same service boundary.

Concrete current issue:

- Shop-facing status changes block final repair-order statuses when a non-void
  invoice has balance due.
- That rule exists in `repair_orders/business_rules.py`.
- Admin bulk status actions call `ro.set_status()` directly.
- If admin is an intentional privileged override, this should be documented.
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

### Priority 4 - Pagination And Query Safety

Likely future slice:

```text
Slice 27: pagination for repair orders, customers, and invoice queue
```

Current list views are acceptable for early development but need pagination and
query hardening before larger datasets.

Likely targets:

- Repair-order list
- Customer list
- Invoice list
- Future payment list
- Vehicle-related lists

Plan:

- Add pagination.
- Preserve stable ordering.
- Review `select_related` / `prefetch_related` usage.
- Review indexes where needed.
- Keep search queries safe and intentionally scoped.

### Priority 5 - Estimate/Insurance Spine

Start the next major domain expansion after lifecycle service boundaries and
remaining authorization limits are addressed.

Proposed model direction:

```text
RepairOrder
  -> Estimate
  -> EstimateLineItem
  -> Supplement
  -> InsuranceClaim
```

Do not jump to payment processor integration before estimates, claims, and
invoice lineage are clearer.

### Priority 6 - Production Hardening

Track now, implement later.

Required later:

- Replace Django `runserver`.
- Split development and production Compose/deployment configuration.
- Harden secure settings.
- Configure HTTPS/proxy headers.
- Configure secure cookies and HSTS.
- Document backups and restore.
- Lock down admin access.
- Design media storage for attachments/photos/documents.
- Define deployment-specific environment management.

## Missing Body-Shop Workflow Areas

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

- Django checks
- Missing migration checks
- Migrations
- Tests
- Docker build/runtime smoke
- `/healthz/`

Missing quality gates:

- Ruff or equivalent linting
- Black formatting
- mypy/type checking
- Coverage reporting and optional threshold
- pre-commit

These are useful as the app grows, but permissions and lifecycle-rule
centralization are higher architectural priorities.
