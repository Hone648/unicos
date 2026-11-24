# Project Context

Unicos is a web-based body shop repair order management app.

The app helps a shop track repair work from intake through completion and
payment. Local Docker Compose is the current development runtime. The first
planned deployment is a controlled beta on one shop's LAN. Internet-hosted
deployment remains the long-term goal.

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

PR #64 shipped intake from customer and active vehicle records. The form
carries the customer and preselects the sole eligible vehicle or the active
vehicle that staff started from. It also supports choosing among multiple
vehicles and returning to the source record on Cancel. The repair-order
list remains a general entry point.

Shop views and Django admin share a repair-order transition policy. Managers
and Owners/Admins give a reason to cancel an eligible order or reopen a
Closed or Canceled order. Staff with the required permissions can record
payment from a balance warning and then retry the status change. The payment
service rechecks the signed continuation under repair-order-first,
invoice-second locking.

The approved beta topology uses one dedicated Linux PC, Docker Compose,
PostgreSQL, and LAN-only browser access. An external NVMe is available for
local backups. The initial beta has no off-site copy, so the shop can lose
both the system and its backups in a site-wide failure. Secure deployment,
restricted administration, private media and scanning, and tested recovery
are planned work. Before entering real data, require evidence for the
[acceptance gates](SLICE_PLAN.md#lan-beta-acceptance-gates), including
verification of the shop's tax setup.

Remaining gaps include broader object-level authorization, richer insurance
claims, scheduling, repair planning, supplement-to-invoice handling, and
broader reporting. Estimate guidance and payment-form usability remain
workflow follow-ups. See the [roadmap](ROADMAP.md).
