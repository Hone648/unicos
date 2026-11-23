# Project Context

Unicos is a web-based body shop repair order management app.

The app is intended to help a shop track repair work from intake through
completion and payment. The intended shop has internet access, so the app is
expected to become internet-accessible / hosted in the future. Local Docker
remains the current development runtime.

Primary business needs:

- Customer contact tracking
- One or more vehicles/VINs per customer
- Work intake
- Work-in-progress tracking
- Owed/paid payment tracking
- Web-based browser access for shop staff
- Future internet-accessible hosted deployment

The app provides staff login, customer and vehicle management, a shop
dashboard, and a repair-order workspace with status history, a communication
log, and local attachment storage. Estimates support line items, insurance
fields, supplements, approval capture, printing, and conversion to draft
invoices. Billing includes an invoice queue, line items, tax totals, printable
invoices, and payments. Operational reporting offers date and status filters
and CSV exports.

Shop views and Django admin share a repair-order transition policy. Managers
and Owners/Admins give a reason to cancel an eligible order or reopen a
Closed or Canceled order. Staff with the required permissions can record
payment from a balance warning and then retry the status change. The payment
service rechecks the signed continuation under repair-order-first,
invoice-second locking.

The app runs in local development. Production readiness still requires secure
deployment and admin access, broader object-level authorization, backup and
restore procedures, and production media storage, serving, and scanning.
Workflow gaps include richer insurance claims, scheduling, repair planning,
supplement-to-invoice handling, and broader reporting. Near-term follow-ups
include intake from customer and vehicle records, estimate guidance, and
payment-form usability. See the [roadmap](ROADMAP.md).
