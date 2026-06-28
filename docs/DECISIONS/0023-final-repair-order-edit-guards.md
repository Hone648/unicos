# 0023: Final Repair Order Edit Guards

Status: Accepted

Decision:

Delivered, Closed, and Canceled repair orders are treated as final for ordinary
repair-order field edits.

Rationale:

- Final repair orders remain visible for shop review, billing review, and
  history inspection.
- Ordinary repair-order field edits are blocked to preserve the meaning of final
  states.
- Direct edit URL access is guarded in the view, not only hidden in the UI.
- Invoice summaries and printable invoices remain available for final repair
  orders.

Scope:

- Status movement is not fully frozen yet.
- Delivered -> Closed remains allowed when existing invoice-balance closure
  rules allow it.
- No model migration was added.
- No custom JavaScript was introduced.
