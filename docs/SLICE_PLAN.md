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

- Future candidates include production media serving/storage/scanning/backup,
  supplement-to-invoice handling, repair planning/parts/sublet, and a structured
  customer/insurer contact model.

Slice order can change after review. Each slice should stay narrow, validate its
own acceptance criteria, and avoid pulling future scope forward without an
explicit decision.

Slice 48: Texas estimate/invoice tax totals (branch `feat/estimate-tax-totals`):

- Configurable combined sales tax rate via `SHOP_SALES_TAX_RATE` (default
  `0.0825`), read/normalized as a Decimal in `[0, 1]` and failing loudly at
  startup on invalid input.
- Shared `app/core/tax.py` utility: money/rate quantization (`ROUND_HALF_UP`),
  `calculate_tax`, and Texas default taxability by line-item type
  (labor/sublet/misc not taxable; parts/materials taxable).
- `Estimate` gains `tax_rate`/`taxable_subtotal`/`tax_amount` plus
  `total_amount` and `customer_responsibility` properties; `estimated_total`
  stays the pre-tax subtotal. `Invoice` gains `tax_rate`/`taxable_subtotal`.
  Estimate and invoice line items gain `is_taxable`.
- Recalculation derives taxable subtotal and tax from taxable line items and the
  snapshotted rate; estimate-to-invoice conversion copies the rate and per-line
  taxability so converted totals match the approved estimate.
- Slice 48 originally shipped two data backfills. Slice 49 retires those
  operations and keeps their migration IDs.
- No new dependencies, no shop profile/admin model, no external tax lookup.
  ADR 0051.

Slice 49: tax migration safety (branch `fix/tax-migration-safety`):

- Both published `0005` migration IDs remain in the graph as no-ops.
  The `0006` migrations add a tax-breakdown marker. Existing documents keep
  their amounts and show the saved tax without unverified rates, taxable
  subtotals, or line taxability.
- An already-migrated database keeps its current amounts. ADR 0051 documents
  backup-based recovery and rollback limits for values overwritten by Slice 48.
- Estimate conversion copies the approved amount, saved rate, and line flags.
  Itemized invoice tax is read-only in shop and admin forms. Manual invoices
  continue to allow tax entry.
- Repricing an unverified draft requires staff to confirm the rate and each
  line's taxability through Review Tax. The application recalculates the
  confirmed breakdown before normal pricing edits resume.

Merged follow-ups after Slice 49:

- PR #60 (`e669cd4`) adds the balance-due warning's payment shortcut and
  returns staff to the pending repair-order status action after payment.
- PR #61 (`5bece09`) reorganizes the repair-order detail page around the
  job overview, next action, billing, and activity. It also records and
  displays the Closed date.
- PR #62 (`8b6ea68`) enforces routine status transitions across shop views and
  Django admin, adds reason-required cancel and reopen actions, and revalidates
  payment shortcuts at the billing write boundary.
- PR #64 (`7bb8ae1`) adds repair-order intake from customer and active vehicle
  records, preserves the list entry point, and improves narrow-screen intake
  and vehicle identification.

The unnumbered documentation pass reconciled the
[staff walkthroughs](USER_MANUAL.md#20-common-workflows),
[architecture](ARCHITECTURE.md), and [roadmap](ROADMAP.md) with PRs #60–#62.
These documents now also reflect the intake workflow shipped in PR #64.

## LAN beta slices

This plan uses the approved LAN slice sequence for the controlled beta under
[ADR 0052](DECISIONS/0052-lan-beta-deployment-topology.md). LAN-00 records the
architecture. LAN-01 through LAN-14 are planned work. The implementation
choices and decision statuses are recorded in the ADRs.

| Slice | Approved scope | Planned work and evidence |
| --- | --- | --- |
| LAN-00 | ADR and documentation baseline | Record the approved topology and backup constraints, proposed controls, open decisions, and acceptance gates. |
| LAN-01 | Deployment settings and secrets | Record the deployment prerequisites. Prepare separate beta settings and runtime secret delivery. Check secure defaults and secret handling in isolation. |
| LAN-02 | Production application runtime | Build a versioned application image with the proposed Gunicorn runtime and locally available browser assets. Run deployment checks and rehearse explicit migrations and restart with separate runtime and migration privileges. |
| LAN-03 | LAN networking, HTTPS, and database isolation | Choose the service name and certificate strategy. Implement proxy, TLS, network controls, and private PostgreSQL access. Verify trust and renewal, access from approved devices, and denial from disallowed networks. Confirm that Django and PostgreSQL have no published host ports. |
| LAN-04 | Private persistent media and authorized serving | Persist private media and enforce existing attachment authorization on downloads. Test role and object checks, direct URL denial, and persistence across container recreation. |
| LAN-05 | Automated local NVMe backups | Automate coordinated, encrypted local backup sets for PostgreSQL, media, and recovery material. Verify backup integrity and record failures. |
| LAN-06 | Restore and disaster recovery | Restore to an isolated target. Compare observed data loss and downtime against agreed RPO and RTO and verify workflows and attachment authorization. Document site-loss limits and fallback. |
| LAN-07 | Authentication and administrative security | Check named accounts and least-privilege roles. Restrict Django admin and SSH, and verify denied access, revocation, and local recovery. |
| LAN-08 | Attachment security and malware controls | Keep upload validation and add screening and quarantine. Verify that scanner failure and suspect uploads keep files unavailable. |
| LAN-09 | Logging, monitoring, and health | Add logs, health checks, alerts, and an operator runbook. Demonstrate response to a simulated incident. |
| LAN-10 | Updates and rollback | Rehearse an image upgrade, an application rollback, and recovery after an incompatible migration. Record release and fallback decisions. |
| LAN-11 | Multi-user and LAN acceptance | Use synthetic records to exercise concurrent staff sessions, role boundaries, and supported browsers and devices on the implemented LAN. Recheck trusted access, network isolation, and browser assets during a WAN interruption. |
| LAN-12 | Shop workflows and failure testing | Exercise synthetic shop workflows, representative failures, and the staff fallback. Verify shop-specific tax configuration and estimate-to-invoice totals. Obtain readiness sign-off before live use. |
| LAN-13 | Beta installation and onboarding | Install the approved release on the shop host. Repeat the deployment checks on the installation, then onboard named users within the approved scope and operating window. |
| LAN-14 | Beta feedback and stabilization | Review incidents, staff feedback, backup evidence, and support. Decide whether to continue, extend, or suspend the beta. |

### LAN beta deployment prerequisites

Record the following prerequisites in LAN-01. Confirm host, OS, and power
readiness for the runtime environment before LAN-02. Verify deployed network
controls in LAN-03 once they are implemented. Recheck the prerequisites on
the shop installation in LAN-13.

- **Host.** Identify the dedicated Linux PC, its operator, and its CPU,
  memory, and storage needs. Reserve capacity for persistent database and
  media data, logs, and updates. Confirm access to the external backup NVMe.
- **Operating system.** Select a supported Linux release compatible with
  Docker Engine and Compose. Plan OS updates, local console recovery, and
  maintenance access.
- **Network.** Identify the shop network owner, approved devices and
  management path, private address and DNS requirements, and the guest and
  WAN boundaries. Document what the router and firewall must enforce.
- **Power.** Identify power dependencies for the PC, network equipment, and
  backup drive. Plan outage handling and controlled shutdown and restart.
  Evaluate power protection, including a UPS, with the shop operator.

## LAN beta acceptance gates

Record evidence and sign-off for each phase before moving to the next.

| Phase | Exit gate |
| --- | --- |
| Architecture (LAN-00) | Review approved decisions, outstanding choices, and the limits of one host and one site. |
| Isolated settings and runtime (LAN-01 to LAN-02) | Record deployment prerequisites. Verify beta settings and secret handling in isolation. A versioned release starts, serves local assets, applies migrations explicitly, and passes deployment checks. |
| LAN boundary and private media (LAN-03 to LAN-04) | After implementing the LAN controls in LAN-03, demonstrate trusted HTTPS, certificate renewal, and denied network access from disallowed devices or networks. Confirm private database access. In LAN-04, verify persistent media and authorized-only downloads. |
| Local backup and recovery (LAN-05 to LAN-06) | Demonstrate automated, verified encrypted backups to the external NVMe and an isolated restore within agreed RPO and RTO. Record the recovery runbook and the residual risk of keeping backups at one site. |
| Security and operations (LAN-07 to LAN-10) | Demonstrate named accounts, role and admin restrictions, scanner failure and quarantine handling, monitoring and alert response, and release rollback and recovery. |
| Pre-beta readiness (LAN-11 to LAN-12) | In LAN-11, verify simultaneous staff use across roles and supported LAN clients. In LAN-12, use synthetic records to exercise customer and vehicle intake, estimates, invoices, payments, closure, attachments, and failure and fallback scenarios. Verify the shop's tax rate and line-item treatment and validate estimate-to-invoice totals. Obtain operator and shop-owner sign-off on the evidence and residual single-site risk before using real data. |
| Installation and stabilization (LAN-13 to LAN-14) | Confirm the shop installation passes its deployment checks before onboarding. Limit live use to the approved cohort and scope. Review incidents, backups, support, and feedback. Record the continuation or suspension decision. Any internet-hosted release needs a separate readiness review. |
