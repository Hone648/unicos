# 0029: Authorization Matrix And Permission Helpers

Status: Accepted

Decision:

Use the existing baseline role groups as inputs for centralized shop-facing
application permissions in `accounts.authorization`.

Rationale:

- Existing role groups were previously names only.
- View access is no longer only login-based for major shop-facing views.
- Permission checks are centralized in `accounts.authorization`.
- Superusers and `Owner/Admin` retain full app-level access.
- `is_staff` is not treated as a shop permission.
- Templates may hide actions, but view checks are authoritative.
- Technician access is intentionally conservative until assigned-repair-order
  semantics exist.

Scope:

- Applies to shop-facing Django views.
- Django admin remains outside the shop-facing helper for now and continues to
  use Django admin/staff/superuser authorization.
- No object-level permission model was added.
- No model changes or migrations were added.
- No service-layer lifecycle refactor was added.
- No broad UI redesign was introduced.
