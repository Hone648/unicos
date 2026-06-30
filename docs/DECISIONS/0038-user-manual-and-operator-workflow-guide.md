# 0038 — User Manual and Operator Workflow Guide

## Context

The repo has developer- and project-facing documentation: architecture docs,
a roadmap, a slice plan, and ADRs covering every significant implementation
decision. It does not have operator-facing documentation explaining how a shop
user should use the app day-to-day.

As the implemented feature set has grown to include customers, vehicles, repair
orders, estimates, supplements, invoice conversion, billing, payments, and
closure rules, the workflow is no longer obvious to a first-time user reading
the code or the developer docs.

## Decision

Add `docs/USER_MANUAL.md` — a single operator-facing manual that covers the
current implemented workflow from customer intake through repair-order closure.

The manual is scoped to what the app actually does, documents limitations
honestly, and is written for a non-developer shop user rather than a developer.
It covers all implemented areas: customers, vehicles, repair orders, estimates,
line items, supplements, printing, approval lifecycle, estimate-to-invoice
conversion, invoices, payments, closure rules, common workflows, a
troubleshooting FAQ, and a glossary.

A link from README.md points to the manual. SLICE_PLAN.md and ROADMAP.md are
updated to mark this slice complete.

## Consequences

- New shop staff have a reference document for daily use.
- The permission matrix documented in the manual reflects the actual
  implemented role/permission assignments in `accounts.authorization`, including
  the counterintuitive fact that the "Estimator" role can view but not create
  or edit estimates in shop-facing views.
- Current limitations (one invoice per repair order, no multi-estimate merge,
  no reopen, no PDF export, local-only deployment) are stated plainly so
  operators are not surprised.
- No app code, templates, migrations, or settings changed.
