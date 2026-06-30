# 0040: Billing Service Boundary

Status: accepted

## Context

Billing mutations were previously enforced directly in shop-facing views. As
invoices, line items, payments, and repair-order final-state rules grew, those
checks became important business rules rather than view plumbing.

## Decision

Centralize billing lifecycle and mutation rules in `billing.services` for:

- issuing invoices
- voiding invoices
- recording payments
- creating invoice line items
- editing invoice line items

Payment recording locks the invoice row with `select_for_update()` inside a
transaction before checking balance and saving the payment.

## Consequences

- Views remain responsible for fetching records, rendering forms, redirects, and
  user messages.
- The service layer owns final-repair-order blocks, void-invoice blocks, issue
  state rules, line-item total checks, payment amount checks, overpayment
  checks, and payment status synchronization.
- This does not add billing models, auth behavior, payment processing, or admin
  override workflows.
