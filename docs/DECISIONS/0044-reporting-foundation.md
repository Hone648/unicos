# 0044. Reporting foundation

## Status

Accepted

## Context

- Managers need a quick read-only operational snapshot without using Django
  admin or scanning every list page.
- The app already has repair-order, billing, and estimate data that can support
  basic counts and attention queues.
- Reporting can expose sensitive business information, so it should not inherit
  broad dashboard visibility by default.
- Object-level reporting scope, exports, date ranges, and deeper analytics need
  more design and are not required for the first reporting slice.

## Decision

- Add a server-rendered `/reports/` page in the existing `core` app.
- Gate the page with a dedicated `reports.view` app permission.
- Grant initial access to Owner/Admin, Manager, Read-only, and superusers.
- Deny initial access to Front Desk, Estimator, and Technician.
- Build the first report from existing models only: repair orders, invoices,
  payments, and estimates.
- Keep the report read-only. Do not add exports, charts, filters, new models, or
  new mutation workflows in this slice.
- Defer per-object reporting scope. Detail links still rely on their existing
  view authorization.

## Consequences

Positive:

- Managers and reviewers get one place to inspect core operational state.
- Reporting access is explicit and testable.
- The slice adds useful visibility without changing domain models or runtime
  deployment assumptions.

Trade-offs:

- The report is intentionally basic and global for users with `reports.view`.
- Date ranges, CSV/export, aging, revenue, and cycle-time reporting remain
  future work.
- Future scoped reporting must revisit how aggregate results interact with
  object-level authorization.
