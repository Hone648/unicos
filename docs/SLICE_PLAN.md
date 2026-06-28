# Slice Plan

Planned slices:

1. Slice 1: project scaffold
2. Slice 1.1: Docker build hygiene and scaffold hardening
3. Slice 2: accounts/auth baseline and web-capable deployment docs
4. Slice 3: customer and vehicle models (customers app, vehicles app, VIN validation, admin)
5. Slice 4: repair order/status/status history (RepairOrder, RepairOrderStatusHistory, controlled TextChoices status, admin)
6. Slice 5: admin operational usability pass for customer, vehicle, repair order, and status history admin screens (display methods, actions, filters, select_related, read-only history)
7. Slice 6: billing foundation (billing app, Invoice one-to-one with RepairOrder, Payment linked to Invoice, admin, payment status sync)
8. Slice 7: repair-order workspace (shop-facing list/detail views, status update POST, search/filter, read-only invoice summary, login required)
9. Slice 8: UI styling foundation (plain CSS static file, styled base layout, header, nav, cards, tables, forms, status badges — no Tailwind/HTMX/build tooling)
10. Slice 9: HTMX status updates (pinned HTMX 2.0.4, status update form updates badge/history/messages without full reload, POST/redirect fallback preserved)
11. Slice 10: shop-facing repair order create/edit (RepairOrderForm, create/edit views, vehicle-belongs-to-customer validation, audit field wiring, no status exposure)
12. Slice 11: shop-facing customer and vehicle management (customer list/detail/create/edit, vehicle create-for-customer/detail/edit, nav links, dashboard card, repair order form workspace links)
13. Slice 12: shop-facing billing workflow (invoice create-for-repair-order, invoice edit, payment create, billing URLs, invoice summary partial on repair-order detail, payments table)
14. Slice 13: invoice line items foundation (InvoiceLineItem, subtotal recalculation, line-item create/edit, invoice summary line-item table)

Slice order can change after review. Each slice should stay narrow, validate its
own acceptance criteria, and avoid pulling future scope forward without an
explicit decision.
