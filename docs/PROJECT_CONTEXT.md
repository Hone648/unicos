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

Current implementation includes the core scaffold, staff login/logout, customer
and vehicle management, repair orders with status history, shop-facing repair
order workflows, billing records, invoice line items, payments, printable
invoices, dashboard visibility, and an invoice queue.

The app is still local-development only and is not production-ready. Major
readiness gaps include domain-specific authorization, centralized lifecycle
services, production deployment hardening, backups/restore, media storage, list
scalability, and missing body-shop workflow objects such as estimates,
insurance claims, attachments, scheduling, and reports.
