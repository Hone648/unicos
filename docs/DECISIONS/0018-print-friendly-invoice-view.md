# 0018: Print-Friendly Invoice View

Status: Accepted

Decision:

Add a read-only invoice detail/print view so staff can present a complete,
printable invoice to customers directly from the browser without needing a
PDF generator or third-party service.

**A read-only invoice detail/print view has been added**

The view is accessible at `/billing/invoices/<pk>/` and requires login. It is
GET-only and performs no mutations. The view renders all relevant invoice data:
invoice metadata, repair order, customer, vehicle, line items, totals, and
payments.

**Browser print is used instead of server-side PDF generation**

Staff can use the native browser print dialog (`Ctrl+P` / `Cmd+P`) to print or
save the invoice as a PDF. This requires no additional dependencies, no server
load, and works in any modern browser. A plain on-screen hint guides staff to
use `Ctrl+P`.

No custom JavaScript is introduced. The print button in the action bar is a
plain text hint, not a `window.print()` call.

**Print CSS hides app chrome**

An `@media print` block in `unicos.css` hides the site header, flash messages,
and the screen-only action bar. The invoice document renders on a white
background without card borders or shadows. Tables remain readable.

**The view is intentionally read-only**

The invoice detail template contains no forms. No mutation of invoice, line
item, payment, or repair order data is possible from this page.

**Screen actions remain available**

When viewing on screen, staff can navigate to Edit Invoice, Add Line Item, and
Record Payment from the action bar. Record Payment is hidden when the invoice is
fully paid or void, matching the behavior in the repair-order detail invoice
summary.

**View/Print Invoice link added to repair-order invoice summary**

The `_invoice_summary.html` partial now includes a View/Print Invoice link when
an invoice exists. Existing Edit Invoice, Add Line Item, and Record Payment
actions are preserved.

**Out of scope for this slice**

- PDF generation
- Email invoices
- Payment links
- Customer portal
- Signatures
- Estimate approvals
- Accounting export
- Invoice numbering automation
- Invoice status workflow changes
- Invoice/payment/line-item delete workflow
- API endpoints
- HTMX expansion beyond existing status update
- Tailwind or any frontend build tooling
- Custom JavaScript
