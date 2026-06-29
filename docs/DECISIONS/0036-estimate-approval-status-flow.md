# 0036: Estimate Approval Status Flow

Status: accepted

## Context

Estimates already support draft, submitted, approved, declined, and expired
status values. Before estimate-to-invoice conversion, those values need a small
controlled lifecycle instead of arbitrary form edits.

## Decision

Estimate status changes are handled by explicit POST actions backed by
`estimates.services.transition_estimate_status()`.

The lifecycle is intentionally small:

```text
draft -> submitted
submitted -> approved
submitted -> declined
submitted -> expired
approved/declined/expired -> terminal
```

Normal shop-facing estimate forms no longer expose `status`. Once an estimate
leaves draft, normal estimate edits and estimate line-item mutations are
blocked. Printable estimate output remains available.

## Rationale

- Keeps approval semantics predictable before invoice generation is added.
- Makes invalid transitions testable in one service layer.
- Avoids status history, reopen, revision, signature, and conversion scope until
  the core lifecycle is stable.

## Consequences

- There is no reopen or revise flow in this slice.
- There is no estimate status history table yet.
- Future invoice generation should start from an approved estimate, but that
  conversion remains deferred.
- Supplements still start as draft estimates and remain separate from invoice
  behavior.
