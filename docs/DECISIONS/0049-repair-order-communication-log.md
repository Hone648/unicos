# 0049. Repair-order communication log

## Status

Accepted

## Context

Unicos needed a lightweight way to record customer, insurer, adjuster, vendor,
tow-provider, and internal communication history on a repair order. The roadmap
tracked customer communication and authorization history as a workflow gap, but
a full CRM/contact model and external messaging integrations are not ready.

## Decision

Add a `communications` app with `CommunicationEntry` records scoped to
`RepairOrder`.

Each entry records when communication happened, direction, channel, contact
role/name, summary, optional next step/outcome, whether it relates to
authorization, and who logged it.

Reuse existing repair-order permissions:

- Viewing follows repair-order visibility.
- Creating requires repair-order manage or change-status permission plus
  repair-order object visibility.

Keep the workflow create-only in the shop-facing UI. Do not add edit/delete,
global inboxes, structured contacts, email/SMS integrations, reminders, portal
features, signatures, or file uploads in this slice.

## Consequences

Positive:

- Staff can capture communication history without leaving the repair order.
- Estimators can log communications because they already participate in repair
  order status workflow.
- Read-only and Technician-only users can view communication entries only where
  they can view the repair order, but cannot add entries.

Trade-offs:

- Contact names are free text.
- Communication entries are not customer-level records.
- There is no outbound/inbound messaging automation.

## Future work

- Structured customer/insurer/adjuster contacts.
- Customer-level and global communication views.
- Follow-up tasks or reminders.
- Email/SMS integrations if workflow needs justify them.
