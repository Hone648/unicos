# 0041: Object Authorization Policy Scaffold

Status: accepted

## Context

Unicos had a centralized app-level role and permission matrix in
`accounts.authorization`, but shop-facing views did not have an explicit
object-level policy layer. That made future technician assignment rules and
per-record review harder to reason about.

## Decision

Add `accounts.policies` for object-specific authorization decisions and enforce
those policies in high-value repair-order, estimate, and billing views.

The policy layer keeps the existing role matrix as the foundation. It adds
repair-order object scope, including technician access limited to repair orders
assigned through `RepairOrder.assigned_to`.

## Consequences

- Shop-facing views now have two authorization layers: app-level permission
  decorators and object-level policy checks.
- Technicians can view assigned repair orders but not unrelated repair orders.
- Estimate and invoice policies inherit repair-order object scope.
- Billing services still own lifecycle and business-state rules.
- Django admin policy enforcement remains future work.
- Full customer/vehicle object policies, multi-shop tenancy, and admin override
  workflows remain future work.
