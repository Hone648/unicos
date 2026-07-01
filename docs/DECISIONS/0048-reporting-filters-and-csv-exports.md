# 0048. Reporting filters and CSV exports

## Status

Accepted

## Context

Slice 41 added the first read-only `/reports/` operational snapshot behind the
`reports.view` permission. Managers and reviewers then needed basic ways to
narrow the snapshot and export the same filtered data for review outside the
app.

The app still does not have a broader reporting warehouse, background jobs,
charts, or a per-object aggregate authorization strategy.

## Decision

Extend `/reports/` with GET-based filters for:

- start and end date
- repair-order status
- invoice status
- estimate status

Add CSV exports for repair orders, invoices, and estimates. CSV links preserve
the active filters. Invalid filters render form errors instead of exporting.

Keep reports read-only and preserve the `reports.view` permission gate. Do not
add new models, scheduled reports, charts, JavaScript, or background jobs.

## Consequences

Positive:

- Managers can narrow operational snapshots without leaving the reports page.
- CSV exports use the same filter semantics as the on-page tables.
- The slice improves reporting usefulness without changing domain models or
  deployment assumptions.

Trade-offs:

- Reporting remains global for users with `reports.view`.
- CSV generation is request/response only.
- Charts, revenue, receivables/aging, cycle-time reporting, and scoped
  aggregate authorization remain future work.
