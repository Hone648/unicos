# 0009: Django Admin as Operational Interface

Status: Accepted

Decision:

Use Django admin as the current operational interface for shop staff through
Slice 5 (admin operational usability pass). Custom shop-facing UI is deferred.

Rationale:

- Django admin provides search, filter, list, create, and edit for all domain
  models without requiring any frontend work.
- The current priority is establishing correct domain models and workflows,
  not a polished interface.
- Starting with admin keeps implementation simple and lets the shop workflow
  be validated before investing in a custom UI.

**Admin actions call model methods, not bulk ORM updates**

Status-changing admin actions (e.g. "Mark as: Estimating") iterate selected
repair orders and call `RepairOrder.set_status()` on each one rather than
using `queryset.update()`. This ensures:

- Status history is created for every change.
- Invalid status values are rejected by the model.
- Transient context (changed_by, note) is correctly attached to each history
  record.

Bulk `.update()` would bypass model `save()`, breaking the history invariant.

Deferred:

- Custom shop-facing UI (Slice 7 or later)
- Billing and repair line items
- Invoice and payment workflows
