# 0017: Invoice Line Items Foundation

Status: Accepted

Decision:

Invoice line items have been added as the first itemized billing layer. Line
items belong to invoices and represent labor, parts, materials, sublet, or misc
charges.

Rationale:

- Itemized invoices make billing explainable without adding inventory, labor
  rate tables, or estimate workflows.
- Line item subtotal recalculation updates `Invoice.subtotal`, so invoice total
  continues to use the existing `subtotal + tax_amount` behavior.
- Existing `Invoice.tax_amount` remains manually controlled.
- Existing payment validation remains authoritative.
- Line-item edits are guarded from making invoice total less than amount paid.

Deferred:

- Line-item deletion
- Parts inventory
- Labor rate tables
- Discounts
- Tax automation
- Estimates
- PDF invoices
- Email invoices
- Accounting exports
- HTMX expansion
- Frontend build tooling
