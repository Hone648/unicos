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
15. Slice 14: printable invoice view (read-only invoice detail/print page, browser-print CSS, View/Print Invoice link from repair-order summary)
16. Slice 15: generated document numbers (system-generated RO-YYYY-NNNNNN and INV-YYYY-NNNNNN; DocumentNumberSequence model in core; staff no longer type numbers manually)
17. Slice 16: invoice lifecycle actions (Issue Invoice POST action sets status=issued and issued_at; Void Invoice POST action sets status=void; payments blocked for void invoices; lifecycle buttons on invoice detail and RO summary)
18. Slice 17: void invoice edit guards (void invoices become billing-read-only; invoice edit, line-item create/edit, and payment create blocked with redirect; UI actions hidden for void invoices; no model changes)
19. Slice 18: repair-order closure rules (final-status transitions blocked when non-void invoice has balance due; void invoices and no invoice allow closure; helper in business_rules.py; HTMX and non-HTMX both guarded)
20. Slice 19: final repair-order edit guards (delivered, closed, and canceled repair orders remain visible but block ordinary repair-order field edits; Delivered -> Closed remains allowed)
21. Slice 20: final repair-order billing guards (final repair orders remain billing-visible but block shop-facing invoice, line-item, payment, issue, and void mutations)
22. Slice 21: CI hardening (missing migration check, migration application, Docker build/runtime smoke, and `/healthz/` validation)
23. Slice 22: dashboard workflow visibility (read-only counts/lists for active repair orders, ready-for-pickup work, unpaid invoices, closure blockers, and recently updated repair orders)
24. Slice 23: billing invoice queue (read-only `/billing/invoices/` list with status filters, search, and links to invoice/repair-order detail)
25. Slice 24: documentation reality check / readiness roadmap (current capabilities, production-readiness gaps, authorization gap, service-layer direction, missing workflow areas, scalability, validation, and quality-gate roadmap)
26. Slice 25: authorization matrix and permission helpers (central app-level role/permission matrix, shop-facing view enforcement, and permission-aware action visibility)
27. Slice 26: repair-order lifecycle service boundary (centralized status transition service in services.py; unpaid-invoice block enforced by service for views, admin actions, and admin form saves; set_status routes through service; _apply_status_change private fallback for test setup; no migrations)
28. Slice 27: list pagination and query safety (core.pagination helper; paginate_queryset and pagination_querystring; 25-item page size; safe invalid/out-of-range page handling; pagination partial template; repair-order, customer, and invoice list views paginated; no migrations; no new dependencies)

29. Slice 28: form validation and data integrity hardening (VehicleForm year range; InvoiceLineItemForm quantity/unit-price field-level clean; PaymentForm amount field-level clean; no migrations)

Likely next implementation slices:

- Slice 29: estimate/insurance spine or advanced search/filtering

Slice order can change after review. Each slice should stay narrow, validate its
own acceptance criteria, and avoid pulling future scope forward without an
explicit decision.
