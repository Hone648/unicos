# 0039: Estimate Approval Capture

Status: accepted

## Context

Estimate approval was previously status-only. A submitted estimate could be
marked approved without recording whether approval came from the customer,
insurer, both parties, or another source.

## Decision

Capture approval evidence on the shop-facing approve action:

- approval source
- approval contact name
- optional approval reference
- optional approval note
- server-set approval timestamp

Approved estimates must have approval source, approval contact name, and
approved timestamp before they can be converted into an invoice draft.

## Consequences

- Existing approved local estimates without approval metadata are not considered
  convertible until approval capture exists.
- Conversion now requires approval capture in addition to approved status, line
  items, no prior conversion, and no existing repair-order invoice.
- No signatures, uploads, customer portal approval, approval email links, or
  multiple approval history records are implemented yet.
