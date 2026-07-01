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
30. Slice 29: estimate and insurance spine (new estimates app; Estimate model linked to RepairOrder via PROTECT; multiple estimates per RO; status lifecycle; insurance company/claim number/deductible/estimated total fields; generated EST-YYYY-NNNNNN numbers via core document-number sequence; shop-facing create/detail/edit views from repair-order detail; estimate summary on RO detail; admin; estimates reuse repair-order permissions; invoice behavior unchanged; estimates + core document-type migrations)
31. Slice 30: estimate line items and supplements (EstimateLineItem model with CASCADE to Estimate; line-item create/edit/POST-delete; estimated_total recalculated from line items when present, manual otherwise; estimate edit disables estimated_total when line items exist; supplement lineage via Estimate.kind=supplement + parent_estimate self-FK with clean() validation; supplement create workflow from estimate detail; line items and supplement links on estimate detail; admin inline + EstimateLineItem admin; estimates reuse repair-order permissions; invoice/billing behavior unchanged; one estimates migration)
32. Slice 31: Docker smoke readiness hardening (CI/runtime readiness checks tightened; no domain changes)
33. Slice 32: printable estimate output (read-only browser-printable estimate page; print link from estimate detail; print CSS; line-item totals, manual-total fallback, insurance, customer, vehicle, repair-order, supplement parent, and notes context; no PDF generation and no domain changes)
34. Slice 33: estimate approval status flow (centralized estimate status transition service; explicit POST status action endpoint; draft -> submitted and submitted -> approved/declined/expired; submitted and terminal estimates are read-only for normal estimate edit and line-item mutation views; status removed from normal shop-facing forms; no migrations; no invoice/billing behavior changes)
35. Slice 34: estimate-to-invoice draft conversion (billing conversion service `convert_estimate_to_invoice`; POST `/estimates/<pk>/convert-to-invoice/` action requiring `billing.manage`; only approved estimates with line items and no existing converted invoice can convert; creates a draft invoice on the same repair order, copies estimate line items into invoice line items, and the invoice total matches the estimate total; nullable `Invoice.source_estimate` FK with partial unique constraint for traceability and duplicate prevention; estimate detail shows "Create Invoice Draft" when convertible and links to the converted invoice otherwise; invoice detail shows a source-estimate reference; invoice issue/void/payment behavior unchanged; one billing migration)
36. Slice 35: user manual and operator workflow guide (`docs/USER_MANUAL.md`; operator-facing guide covering customer, vehicle, repair order, estimate, supplement, print, approval lifecycle, estimate-to-invoice conversion, invoices, payments, closure rules, common workflows, troubleshooting FAQ, and glossary; role/permission table matching actual implemented matrix; honest limitation notes; README link; ADR 0038; docs-only, no app code changes)
37. Slice 36: customer/insurer approval capture (Estimate approval source/contact/reference/note/approved_at fields; approval source/contact required when moving submitted -> approved through the shop-facing status action; detail and print show captured approval metadata; estimate-to-invoice conversion requires approval capture in addition to approved status, line items, no prior conversion, and no existing repair-order invoice; admin exposes approval fields; one estimates migration)
38. Slice 37: billing service boundary and payment concurrency guarantee (`billing.services` owns invoice issue, invoice void, payment recording, and invoice line-item mutations; payment recording locks the invoice row with `select_for_update()`; views remain thin; no migrations)
39. Slice 38: object-level authorization policy scaffold (`accounts.policies` object-policy layer; assigned technicians can view only assigned repair orders; repair-order, estimate, and billing views enforce app-level plus object-level authorization; no migrations)
40. Slice 39: Django admin policy decision / ADR (Django admin explicitly defined as an emergency/development back-office console; shop-facing views remain authoritative operator workflow; admin service alignment and audited override path deferred; no migrations)
41. Slice 40: quality gates foundation (Ruff-only lint/format config, development requirements, pre-commit hooks, CI quality job, docs/ADR; no app behavior changes)
42. Slice 41: reporting foundation (read-only `/reports/` page in `core`; `reports.view` permission for Owner/Admin, Manager, Read-only, and superusers; repair-order, invoice, and estimate operational counts; top unpaid invoices, ready-for-pickup ROs, and estimates needing attention; docs/ADR; no migrations)
43. Slice 42: repair-order attachments/media foundation (new `attachments` app; `Attachment` model linked to `RepairOrder` via `PROTECT`; local `FileField` storage under `MEDIA_ROOT/repair_orders/<ro_id>/<uuid>_<basename>`; upload/download/delete views policy-gated; `MEDIA_URL`/`MEDIA_ROOT` configured; development-only media serving under `DEBUG`; allowed extensions jpg/jpeg/png/gif/webp/pdf/txt/csv; 25 MB limit; repair-order detail shows attachment list; admin registration; 26 tests; one attachments migration; ADR 0045)
44. Slice 43: admin service-alignment / override audit (Django admin no longer silently bypasses domain services for high-risk mutations; `EstimateAdmin` routes status changes through `transition_estimate_status` including approval-capture enforcement, `approved_at` readonly, `estimated_total` readonly once line items exist, non-draft estimate line items blocked from admin add/change/delete; `InvoiceAdmin.status` readonly with new `issue_selected_invoices`/`void_selected_invoices` actions backed by `issue_invoice`/`void_invoice`, `subtotal` readonly once line items exist; `InvoiceLineItemAdmin` routes create/edit through `create_invoice_line_item`/`edit_invoice_line_item`; invoice line-item and payment inlines on `InvoiceAdmin` made read-only; `PaymentAdmin` routes creation through `record_payment`, existing payments immutable/non-deletable through admin; `AttachmentAdmin` keeps upload metadata readonly and disables delete; repair-order admin left unchanged (already aligned); admin/service-boundary tests added across `estimates`, `billing`, and `attachments`; no migrations; no user-facing feature changes; ADR 0046)

Post-Slice 43 unnumbered fixes:

- `b0d7dc0 fix: scope repair order vehicles by customer`: New Repair Order form vehicle dropdown is disabled until customer selection; HTMX loads vehicles scoped to the selected customer. This was an unnumbered UX fix, not Slice 44.

Slice-number reconciliation:

- The actual Git-backed sequence above is canonical.
- The originally planned separate Slice 38, "Billing views call services only," was effectively absorbed into actual Slice 37 because `billing.services` now owns invoice issue/void, payment recording, and invoice line-item mutations while views call services.
- Slice 43 was an inserted hardening slice for admin service alignment and override-audit planning.
- This reconciliation is docs-only and does not claim the product Slice 44 number.
- Slice 44 follows this docs-only reconciliation as the next product slice.

45. Slice 44: reporting filters/date ranges and CSV export (`/reports/` adds GET filters for date range, repair-order status, invoice status, and estimate status; CSV exports for repair orders, invoices, and estimates preserve active filters; invalid filters render form errors instead of CSV; reports remain read-only behind `reports.view`; no migrations)
46. Slice 45: attachment hardening / media persistence (Docker Compose mounts named `media_data` at `/app/media`; `MEDIA_URL`/`MEDIA_ROOT` support environment overrides with local defaults; `/healthz/` checks database and media writability; upload validation rejects unsafe filenames, disallowed extensions, MIME/extension mismatches, oversized files, and minimal binary signature mismatches; missing attachment files 404 on download but do not block DB-row deletion; no migrations; ADR 0047)
47. Slice 46: repair-order communication log (new `communications` app with `CommunicationEntry` linked to `RepairOrder` via `PROTECT`; create-only shop-facing form at `/repair-orders/<pk>/communications/new/`; repair-order detail shows latest 10 communication entries; creation reuses repair-order manage/change-status permissions plus object policy; read access follows repair-order visibility; one communications migration; ADR 0049)
48. Slice 47: Bootstrap UI foundation (Bootstrap 5.3 static CSS/JS vendored under `app/static/vendor/bootstrap/`; base layout uses a Bootstrap navbar, collapsible mobile navigation, Bootstrap alerts, and a container shell; high-traffic list/detail/form/report pages use Bootstrap buttons/cards/tables where practical; `unicos.css` remains the domain-specific override layer for statuses, print views, forms, operational layout, and HTMX fragments; no migrations and no business logic changes; ADR 0050)

Post-Slice 45 unnumbered planning step:

- Docs/roadmap renewal after Slice 45 is unnumbered.
- It does not consume product Slice 46.
- Product Slice 46 remains reserved for the next app feature.

Likely next implementation slices:

- Slice 48: production media serving/storage/scanning/backup design or another
  roadmap-approved candidate
- Slice 49: supplement-to-invoice handling, repair planning/parts/sublet, or
  structured customer/insurer contact model

Slice order can change after review. Each slice should stay narrow, validate its
own acceptance criteria, and avoid pulling future scope forward without an
explicit decision.
