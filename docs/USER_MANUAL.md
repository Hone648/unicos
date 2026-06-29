# Unicos User Manual

Unicos is a browser-based body shop workflow app for managing customers, vehicles, repair orders, estimates, invoices, payments, and repair-order closure.

This manual describes the current implemented local-development version of Unicos. It is not a production deployment guide.

---

## Table of Contents

1. [What Unicos Is](#1-what-unicos-is)
2. [Current Limitations](#2-current-limitations)
3. [User Roles and Access](#3-user-roles-and-access)
4. [Dashboard](#4-dashboard)
5. [Customers](#5-customers)
6. [Vehicles](#6-vehicles)
7. [Repair Orders](#7-repair-orders)
8. [Estimates](#8-estimates)
9. [Estimate Line Items](#9-estimate-line-items)
10. [Supplements](#10-supplements)
11. [Printing Estimates](#11-printing-estimates)
12. [Estimate Approval Workflow](#12-estimate-approval-workflow)
13. [Creating an Invoice Draft from an Approved Estimate](#13-creating-an-invoice-draft-from-an-approved-estimate)
14. [Invoices](#14-invoices)
15. [Invoice Line Items](#15-invoice-line-items)
16. [Printing Invoices](#16-printing-invoices)
17. [Issuing and Voiding Invoices](#17-issuing-and-voiding-invoices)
18. [Recording Payments](#18-recording-payments)
19. [Repair Order Closure Rules](#19-repair-order-closure-rules)
20. [Common Workflows](#20-common-workflows)
21. [Troubleshooting / FAQ](#21-troubleshooting--faq)
22. [Glossary](#22-glossary)

---

## 1. What Unicos Is

Unicos is a web-based shop management app designed for the daily workflow of an auto body shop. It tracks the full cycle from customer intake through estimate, insurance claim, invoice, payment, and repair order closure.

All pages are standard browser pages — no special software is required beyond a modern web browser. Every staff member logs in with a username and password. Access is controlled by their assigned role.

The app is organized around the **repair order** as the central record. Everything else — estimates, supplements, invoices, and payments — attaches to a repair order.

---

## 2. Current Limitations

Be aware of these limitations before using Unicos in day-to-day operations.

- **Local development only.** Unicos runs on a single machine using Docker Compose and is not set up for multi-user network access, HTTPS, or production hosting. Do not store real customer data until a hardened deployment is in place.
- **One invoice per repair order.** Each repair order can have only one invoice. If the invoice already exists, a second invoice cannot be created.
- **No estimate queue.** There is no global list of all estimates across the shop. Estimates are accessed through their repair order.
- **No multi-estimate invoice merging.** If a repair order has a primary estimate and one or more supplements, they cannot be merged into a single invoice automatically. Only one approved estimate can be converted to the repair order's invoice.
- **No partial estimate conversion.** Conversion is all-or-nothing. You cannot convert only some line items from an estimate.
- **No estimate reopen or revision workflow.** Once an estimate leaves draft status, it cannot be reopened for editing through shop-facing views. A supplement can capture additional work.
- **No email or PDF generation.** Estimate and invoice output uses the browser's built-in print function. There is no automated email sending or server-side PDF export.
- **No object-level permissions.** All staff with a given role can see and act on all records of that type, regardless of who created them. There are no per-record access restrictions.
- **No technician assignment constraints.** Technicians can view all repair orders, not just their assigned ones.
- **Django admin is separate.** The Django admin interface (if accessible) uses its own authorization system that is not connected to the shop-facing permission helpers described in this manual.
- **Deployment is not production-ready.** See the README for production prerequisites.

---

## 3. User Roles and Access

Every staff user is assigned to one or more roles. Roles control which pages and actions are available. If a button is missing or a page returns a "403 Forbidden" error, the user's role does not have the required access.

**Role summary:**

| Role | What they can do |
|---|---|
| Owner/Admin | All actions across all areas |
| Manager | All actions across all areas |
| Front Desk | Customer intake, vehicle intake, repair order create/edit, view invoices, record payments |
| Estimator | View dashboard, view customers, view repair orders, change repair order status, view invoices |
| Technician | View dashboard, view repair orders |
| Read-only | View dashboard, view customers, view repair orders, view invoices |

**Important notes on roles:**

- View checks in the app are authoritative. Even if a button is hidden, the underlying page enforces the role check server-side.
- Superusers and Owner/Admin have access to everything.
- `is_staff` (Django admin staff flag) does not grant shop-facing permissions.
- A user without any role assignment has no shop-facing access beyond login.
- Roles stack: a user assigned to both Front Desk and Estimator gets the combined permissions of both.

**What each role cannot do (key limits):**

- **Front Desk** cannot create or edit estimates, supplements, or estimate line items. Cannot issue or void invoices. Cannot convert estimates to invoices. Can record payments.
- **Estimator** cannot create or edit repair orders, estimates, supplements, or estimate line items. Cannot manage invoices or record payments. Can view all of the above and can change repair order status.
- **Technician** cannot view customers or billing. Can only view the dashboard and repair order list/detail.
- **Read-only** cannot create or edit anything. Cannot record payments.

---

## 4. Dashboard

**URL:** `/`

The dashboard is the first page shown after login. It gives a quick overview of active shop work.

Sections:

- **Active Repair Orders** — repair orders that are in progress (not delivered, closed, or canceled).
- **Ready for Pickup** — repair orders in "Ready for Pickup" status.
- **Unpaid Invoices** — issued invoices that have a balance remaining.
- **Closure Blockers** — repair orders that cannot move to a final status because of an unpaid invoice.
- **Recently Updated** — repair orders updated most recently, for quick access.

Each item links to the relevant repair order or invoice detail page. The dashboard is read-only; no actions are performed from here.

**Who can see it:** All roles (dashboard.view permission).

---

## 5. Customers

**URL:** `/customers/`

Customers are individual or business contacts. Each customer can have multiple vehicles.

### Viewing the customer list

Go to `/customers/` to see all customers. You can search by name. The list paginates at 25 per page.

### Creating a customer

1. Click **New Customer** from the customer list.
2. Fill in the name fields. For an individual, provide first or last name (or both). For a business, provide the business name.
3. Optionally add phone, email, and address.
4. Click **Save**.

**Who can create/edit customers:** Owner/Admin, Manager, Front Desk (customers.manage).

### Viewing a customer

Click any customer in the list to open the customer detail page. The detail page shows contact information and a list of the customer's vehicles and their associated repair orders.

**Who can view customers:** Owner/Admin, Manager, Front Desk, Estimator, Read-only (customers.view).

### Editing a customer

From the customer detail page, click **Edit Customer**. Change any fields and save.

---

## 6. Vehicles

Vehicles belong to a customer. A vehicle is identified by its VIN (17-character vehicle identification number).

### Adding a vehicle

1. Open the customer's detail page.
2. Click **Add Vehicle**.
3. Enter the VIN, year, make, model, and color. The VIN is normalized to uppercase and validated.
4. Click **Save**.

**Who can add vehicles:** Owner/Admin, Manager, Front Desk (customers.manage).

### Viewing and editing a vehicle

From the customer detail page, click the vehicle to open its detail page. From there, click **Edit Vehicle** to modify any fields.

### Vehicle-customer relationship

A vehicle belongs to exactly one customer. When creating a repair order, the vehicle must belong to the selected customer. Changing the customer on a repair order without changing the vehicle will fail validation.

---

## 7. Repair Orders

**URL:** `/repair-orders/`

A repair order is the central record for each job. It links a customer, a vehicle, and tracks the job's workflow status, estimates, invoice, and notes.

### Repair order numbers

Repair order numbers are system-generated in the format `RO-YYYY-NNNNNN`. Staff do not type these manually.

### Viewing the repair order list

Go to `/repair-orders/` to see all repair orders. You can search by repair order number, customer name, or vehicle. Filter by status using the status tabs. The list paginates at 25 per page.

### Creating a repair order

1. Click **New Repair Order** from the list.
2. Select the customer and vehicle. The vehicle must belong to the selected customer.
3. Optionally set a promised date and add notes.
4. Click **Save**.

The repair order starts in **Intake** status.

**Who can create/edit repair orders:** Owner/Admin, Manager, Front Desk (repair_orders.manage).

### Repair order detail

The detail page shows:
- Customer and vehicle summary
- Current status and status history
- Status update controls
- A summary of all estimates
- Invoice and payment summary
- Action links for creating estimates and invoices

### Status and status history

The current status is shown prominently. The full history of status changes is shown below, including who made each change and when.

**Available statuses (approximate lifecycle):**

```
Intake → In Repair → Ready for Pickup → Delivered → Closed
                                      → Canceled
```

Status transitions are controlled. Not all transitions are available at all times. See [Repair Order Closure Rules](#19-repair-order-closure-rules) for final-status restrictions.

### Changing repair order status

1. From the repair order detail page, use the status update control.
2. Select the new status.
3. Submit. The status history updates immediately.

**Who can change repair order status:** Owner/Admin, Manager, Estimator (repair_orders.change_status). Note: Front Desk cannot change status.

### Final repair orders

Once a repair order reaches **Delivered**, **Closed**, or **Canceled** status, ordinary editing of the repair order's fields is blocked. The detail and history remain fully visible. Some status movement may still be allowed (e.g., Delivered → Closed). Invoice and payment records remain visible but billing mutations are blocked.

---

## 8. Estimates

Estimates capture the proposed scope of work and cost for a repair job. They also hold insurance claim information if the job is insurance-related.

Estimates are accessed from the repair order detail page. There is no global estimate list.

### Estimate numbers

Estimate numbers are system-generated in the format `EST-YYYY-NNNNNN`.

### Estimate statuses

| Status | Meaning |
|---|---|
| Draft | Working estimate; can be edited |
| Submitted | Sent for approval; editing is locked |
| Approved | Approved; can be converted to invoice |
| Declined | Not approved; terminal |
| Expired | Time-lapsed; terminal |

Only **Draft** estimates can be edited through normal shop views.

### Creating an estimate

1. Open the repair order detail page.
2. Click **New Estimate**.
3. Fill in the estimate details:
   - Insurance company name (if insurance)
   - Claim number (if insurance)
   - Deductible amount (if insurance)
   - Estimated total (manual entry until line items exist)
   - Notes
4. Click **Save**.

The estimate starts in **Draft** status.

**Who can create estimates:** Owner/Admin, Manager, Front Desk (repair_orders.manage).

Note: Estimators can view estimates but cannot create or edit them in the current permission model.

### Viewing an estimate

Click the estimate link from the repair order detail page to open the estimate detail page. The detail page shows all estimate fields, line items, supplements, status, and available actions.

**Who can view estimates:** Owner/Admin, Manager, Front Desk, Estimator, Read-only (repair_orders.view).

### Editing an estimate

From the estimate detail page, click **Edit Estimate**. Only draft estimates can be edited. If the estimate has left draft status, the edit button is hidden and the edit page returns an error.

---

## 9. Estimate Line Items

Line items itemize the work and materials in an estimate. Once any line items exist, the estimate total is calculated from them automatically. The manual estimated total field is disabled when line items are present.

### Adding a line item

1. Open the estimate detail page.
2. Click **Add Line Item**.
3. Select the item type (Labor, Parts, Materials, Sublet, or Misc).
4. Enter a description, quantity, and unit price.
5. Click **Save**.

The estimate total updates immediately.

**Who can add/edit/delete line items:** Owner/Admin, Manager, Front Desk (repair_orders.manage). Line item changes are blocked if the estimate is not in Draft status.

### Editing a line item

Click the edit link next to any line item on the estimate detail page.

### Deleting a line item

Click the delete link next to a line item. Deletion is a POST action (not a simple link click) to prevent accidental removal. The estimate total recalculates after deletion.

---

## 10. Supplements

A supplement is a child estimate that captures additional work discovered after the original estimate was approved. Supplements are full estimates — they have their own line items, insurance fields, status lifecycle, and print output.

### Creating a supplement

1. Open the original (parent) estimate detail page.
2. Click **New Supplement**.
3. The supplement form pre-fills insurance and claim fields from the parent. Adjust as needed.
4. Click **Save**.

The supplement appears in the supplements section of the parent estimate's detail page.

**Who can create supplements:** Owner/Admin, Manager, Front Desk (repair_orders.manage).

### Supplement rules

- A supplement must belong to the same repair order as its parent.
- A supplement cannot have its own parent be another supplement (only one level of lineage).
- Supplements have the same lifecycle as ordinary estimates (draft → submitted → approved/declined/expired).

### Supplement-to-invoice limitation

Currently, each repair order has exactly one invoice. If the repair order already has an invoice from the primary estimate, a supplement cannot be independently converted to a second invoice. Plan supplement work around the single-invoice constraint.

---

## 11. Printing Estimates

Each estimate has a browser-printable output page.

### Printing an estimate

1. Open the estimate detail page.
2. Click **Print Estimate** (or navigate to `/estimates/<id>/print/`).
3. The print page shows a clean, print-optimized layout with:
   - Shop and customer information
   - Vehicle details
   - Estimate number and date
   - Insurance information (if present)
   - Line items with individual totals
   - Estimated total (from line items or manual)
   - Notes
   - Supplement parent reference (if a supplement)
4. Use the browser's print function (`Ctrl+P` / `Cmd+P`) to print or save as PDF.

The print page does not include navigation, action buttons, or status controls.

---

## 12. Estimate Approval Workflow

The estimate approval lifecycle controls when an estimate can move to billing. Only the shop-facing status action (not normal estimate edit) changes the status.

### Status transitions

```
Draft → Submitted → Approved
                 → Declined
                 → Expired
```

Approved, Declined, and Expired are terminal. An estimate cannot be moved backward or reopened once it leaves Draft.

### Submitting an estimate

1. Open the estimate detail page (must be Draft).
2. Click **Submit Estimate**.
3. The estimate moves to Submitted. Editing is now locked.

### Approving or declining an estimate

1. Open the estimate detail page (must be Submitted).
2. Click **Approve Estimate** or **Decline Estimate** as appropriate.
3. The estimate moves to the selected terminal status.

### Expiring an estimate

1. Open the estimate detail page (must be Submitted).
2. Click **Expire Estimate**.
3. The estimate moves to Expired.

**Who can change estimate status:** Owner/Admin, Manager, Front Desk (repair_orders.manage).

### Effect on editing

- **Draft** estimates: full editing of estimate fields and line items is available.
- **Submitted / Approved / Declined / Expired** estimates: estimate field editing and line item add/edit/delete are blocked. Print and view remain available.

---

## 13. Creating an Invoice Draft from an Approved Estimate

An approved estimate with line items can be converted into a draft invoice in one action. This copies the estimate line items into the invoice and links the invoice back to the source estimate.

### Conditions required for conversion

All of the following must be true:

1. The estimate status is **Approved**.
2. The estimate has **at least one line item**.
3. The estimate has **not already been converted** to an invoice.
4. The repair order does **not already have an invoice**.
5. The user has the **billing.manage** permission (Owner/Admin or Manager).

If any condition is not met, the "Create Invoice Draft" button does not appear, or the action is blocked with an error message.

### Converting an estimate

1. Open the estimate detail page (must be Approved, with line items).
2. Click **Create Invoice Draft**.
3. The app creates a draft invoice, copies all estimate line items into invoice line items, and redirects to the new invoice detail page.

### What happens during conversion

- A new invoice is created with status **Draft**.
- The invoice number is system-generated (`INV-YYYY-NNNNNN`).
- All estimate line items are copied into invoice line items (type, description, quantity, unit price).
- The invoice total equals the estimate total.
- The estimate is **not changed** — its status, line items, and fields remain as-is.
- The invoice is **not issued automatically**. Payment is not recorded. These are separate steps.

### After conversion

- The estimate detail page shows a **View Invoice** link instead of the "Create Invoice Draft" button.
- The invoice detail page shows a "Created from estimate EST-YYYY-NNNNNN" reference linking back to the source estimate.
- Attempting to convert the same estimate again is blocked.

---

## 14. Invoices

**URL:** `/billing/invoices/`

Invoices record the billable charges for a repair order. Each repair order can have at most one invoice.

### Invoice numbers

Invoice numbers are system-generated in the format `INV-YYYY-NNNNNN`.

### Invoice statuses

| Status | Meaning |
|---|---|
| Draft | Created but not yet issued; can be edited |
| Issued | Issued to the customer; balance is due |
| Partially Paid | Payments have been recorded but balance remains |
| Paid | Fully paid; no balance due |
| Void | Voided; no balance due; billing-read-only |

### Creating an invoice manually

If no estimate exists or you want to create an invoice without going through the estimate workflow:

1. Open the repair order detail page.
2. Click **Create Invoice** (requires billing.manage).
3. Optionally enter a subtotal manually (this will be overridden once line items exist), tax amount, and due date.
4. Click **Save**.

The invoice starts in Draft status.

**Who can create/edit invoices:** Owner/Admin, Manager (billing.manage).

### Viewing the invoice list

Go to `/billing/invoices/` to see all invoices. Filter by status using the tabs. Search by invoice number or repair order number. The list paginates at 25 per page.

**Who can view invoices:** Owner/Admin, Manager, Front Desk, Estimator, Read-only (billing.view).

### Viewing an invoice

Click any invoice in the list, or follow the invoice link from the repair order detail page. The detail page shows status, line items, payments, balance due, and available actions.

---

## 15. Invoice Line Items

Invoice line items work the same way as estimate line items. Once any line items are added, the invoice subtotal is calculated from them and the manual subtotal field is disabled.

### Adding a line item to an invoice

1. Open the invoice detail page (must be Draft status and on a non-final repair order).
2. Click **Add Line Item**.
3. Select type, description, quantity, and unit price.
4. Click **Save**.

The invoice subtotal recalculates.

**Who can add/edit invoice line items:** Owner/Admin, Manager (billing.manage). Blocked for void invoices and invoices belonging to final repair orders.

### Editing a line item

Click the edit link next to the line item on the invoice detail page.

---

## 16. Printing Invoices

Each invoice has a browser-printable output page.

### Printing an invoice

1. Open the invoice detail page.
2. Click **View / Print Invoice**.
3. The print page shows:
   - Shop and customer information
   - Vehicle details
   - Invoice number, issue date, and due date
   - Line items with individual totals
   - Subtotal, tax, and total
   - Payment history and balance due
4. Use the browser's print function to print or save as PDF.

---

## 17. Issuing and Voiding Invoices

### Issuing an invoice

Issuing an invoice marks it as sent to the customer. The issue date is recorded and the balance becomes due.

1. Open the invoice detail page (must be Draft).
2. Click **Issue Invoice**.
3. Confirm the action. The invoice moves to Issued status.

Once issued, the invoice fields and line items are still editable (if the repair order is not final), but payments can now be recorded.

**Who can issue invoices:** Owner/Admin, Manager (billing.manage).

### Voiding an invoice

Voiding cancels an invoice. A voided invoice cannot be paid or edited further.

1. Open the invoice detail page (any non-void status).
2. Click **Void Invoice**.
3. Confirm the action. The invoice moves to Void status.

A voided invoice does not block repair order closure. If the repair order needs to close but the invoice has a balance, consider voiding the invoice or recording a payment to clear the balance.

**Who can void invoices:** Owner/Admin, Manager (billing.manage).

---

## 18. Recording Payments

Payments are recorded against an issued invoice.

### Recording a payment

1. Open the invoice detail page (invoice should be Issued or Partially Paid).
2. Click **Record Payment**.
3. Enter the payment amount, method (cash, check, card, etc.), and an optional reference note.
4. Click **Save**.

The invoice payment status updates automatically. If the payment covers the balance, the invoice moves to Paid. If partial, it moves to Partially Paid.

**Who can record payments:** Owner/Admin, Manager, Front Desk (billing.record_payment).

### Overpayment

The app validates that payments do not exceed the invoice balance. An overpayment attempt returns a validation error.

### Payments on void invoices

Payments cannot be recorded against a void invoice.

---

## 19. Repair Order Closure Rules

A repair order must meet certain conditions before it can move to a final status (Delivered, Closed, or Canceled).

### Unpaid invoice block

If the repair order has a non-void invoice with a balance due (Issued or Partially Paid), the status update to a final status is blocked with an error:

```
Repair order cannot be marked [status] because invoice INV-YYYY-NNNNNN has a balance due.
```

To resolve:
- Record a payment that covers the balance, or
- Void the invoice if the charges are being waived.

Then retry the status update.

### Final-status edit guards

Once a repair order is Delivered, Closed, or Canceled:

- Ordinary repair order field editing is blocked.
- Creating or editing estimates and line items is blocked.
- Invoice edits, line item changes, and payment recording are blocked in shop-facing views.
- The repair order detail, status history, invoice detail, printable invoice, and estimate/print views remain visible.
- Some status transitions may still be allowed (for example, Delivered → Closed is supported).

---

## 20. Common Workflows

### Workflow A: New customer repair (insurance)

1. **Create customer** — go to `/customers/`, click New Customer, enter name and contact info.
2. **Add vehicle** — from the customer detail page, click Add Vehicle, enter VIN, year, make, model.
3. **Create repair order** — go to `/repair-orders/`, click New Repair Order, select customer and vehicle.
4. **Create estimate** — from the repair order detail page, click New Estimate, enter insurance company, claim number, deductible, and notes.
5. **Add estimate line items** — from the estimate detail page, click Add Line Item for each charge.
6. **Print estimate** — click Print Estimate, use the browser print function.
7. **Submit estimate** — from the estimate detail page, click Submit Estimate.
8. **Approve estimate** — click Approve Estimate once approval is confirmed.
9. **Create invoice draft** — click Create Invoice Draft. The app creates a draft invoice with copied line items.
10. **Review invoice** — open the invoice detail, verify line items and total.
11. **Issue invoice** — click Issue Invoice.
12. **Record payment** — click Record Payment, enter amount and method.
13. **Close repair order** — return to the repair order, change status to Delivered, then Closed when ready. The closure is allowed once the invoice balance is zero.

### Workflow B: Insurance estimate with supplement

1. Complete steps 1–8 from Workflow A to create and approve the initial estimate.
2. If additional work is found, open the approved estimate detail page.
3. Click **New Supplement** to create a supplement estimate for the additional work.
4. Add line items to the supplement.
5. Print the supplement.
6. Submit and approve the supplement through the same status workflow.

Note: The repair order can have only one invoice. The initial approved estimate conversion creates that invoice. Supplement charges must be added to the invoice manually as additional line items after conversion, or included in the initial estimate before conversion. There is no automatic supplement-to-invoice merge.

### Workflow C: Customer-pay invoice (no estimate)

1. Create customer, vehicle, and repair order as in Workflow A steps 1–3.
2. From the repair order detail page, click **Create Invoice** (requires billing.manage).
3. Add line items to the invoice.
4. Review the invoice total.
5. Issue the invoice.
6. Record payment when received.
7. Close the repair order when the balance is clear.

### Workflow D: Blocked closure

**Scenario:** You try to move a repair order to Delivered but get a "balance due" error.

1. Open the repair order detail page.
2. Note the invoice number shown in the error.
3. Open the invoice detail page.
4. Either:
   - Click **Record Payment** to clear the balance, or
   - Click **Void Invoice** if the charges are being waived.
5. Return to the repair order detail page.
6. Retry the status update to Delivered.

---

## 21. Troubleshooting / FAQ

**Why can't I edit this estimate?**
The estimate is no longer in Draft status. Once submitted, approved, declined, or expired, the estimate is locked for editing through normal shop views. If additional work needs to be captured, create a supplement.

**Why don't I see the "Create Invoice Draft" button?**
One or more conditions are not met. The button appears only when:
- The estimate is Approved.
- The estimate has at least one line item.
- The estimate has not already been converted.
- The repair order does not already have an invoice.
- Your role has billing.manage access (Owner/Admin or Manager).

Check each condition. If the repair order already has an invoice, navigate to it from the repair order detail page.

**Why can't I convert this estimate?**
If the button was present but the conversion failed, the most likely causes are:
- The repair order already has an invoice (possibly created manually).
- Another user converted the estimate at the same time (duplicate blocked).
The error message will state the specific reason.

**Why is the invoice button missing?**
If you don't see the Issue Invoice or Void Invoice buttons, either your role does not have billing.manage access, or the invoice is already in a state where the action is not applicable (already issued, already void, etc.).

**Why can't I close this repair order?**
The repair order has a non-void invoice with a balance due. Record a payment to clear the balance or void the invoice, then retry the status change.

**Why can't I edit this invoice?**
One of these conditions applies:
- The invoice belongs to a final repair order (Delivered, Closed, or Canceled).
- The invoice is void.
In both cases, the invoice and its line items are read-only.

**Why does this page hide an action button?**
Buttons are hidden when the current user's role does not have the required permission or when the business rule blocks the action (e.g., a draft estimate has no Submit button if the status action is not available). The page's view check is authoritative — hiding a button is cosmetic, but the server enforces the rule regardless.

**Can I create more than one invoice for a repair order?**
No. Each repair order has at most one invoice. If you need to add charges after the initial invoice is created, add them as line items to the existing invoice.

**Can I convert a submitted estimate?**
No. Only **Approved** estimates can be converted. Submit the estimate and then approve it first.

**Can I reopen an approved estimate?**
No. Approved, Declined, and Expired are terminal statuses. An approved estimate cannot be changed back to draft. If additional work is needed, create a supplement.

**I recorded a payment but the invoice still shows a balance.**
The payment amount may have been less than the full balance. Check the payment amount in the payments table on the invoice detail page. Record another payment for the remaining balance if needed.

**A team member can view the dashboard but gets "403 Forbidden" on certain pages.**
Their role does not have access to that area. Check their assigned roles in the Django admin. Assign the appropriate role for the access they need.

---

## 22. Glossary

**Estimate** — A document capturing the proposed scope and cost of work on a repair order. May include insurance information and line items. Goes through a status lifecycle (draft → submitted → approved/declined/expired).

**Estimate Line Item** — A single itemized charge on an estimate. Types: Labor, Parts, Materials, Sublet, Misc.

**Final Status** — Repair order statuses that end the active workflow: Delivered, Closed, Canceled. Final-status repair orders become read-only for most edits.

**Invoice** — A billing document attached to a repair order. Tracks charges (via line items), tax, payments, and balance due.

**Invoice Line Item** — A single itemized charge on an invoice. Copied from an estimate during conversion, or entered manually.

**Payment** — A record of money received against an invoice. Multiple payments can be recorded; they sum to the invoice's total received.

**Repair Order** — The central shop record for a job. Links a customer, a vehicle, a status lifecycle, estimates, and an invoice.

**RO** — Abbreviation for Repair Order.

**Source Estimate** — The approved estimate from which an invoice draft was created. Shown on the invoice detail page as a traceable back-reference.

**Supplement** — A child estimate that captures additional work found after the primary estimate. Supplements have the same fields and lifecycle as regular estimates.

**Terminal Status (Estimate)** — Approved, Declined, or Expired. An estimate in a terminal status cannot be changed.

**Void** — An invoice status meaning the invoice is canceled. Void invoices do not count as unpaid and do not block repair order closure.
