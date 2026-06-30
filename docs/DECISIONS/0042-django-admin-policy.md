# 0042. Django admin policy

## Status

Accepted

## Context

- The app now has app-level authorization and object-level shop-facing policies.
- Shop-facing views enforce policy through `accounts.authorization` and
  `accounts.policies`.
- Service boundaries exist for repair-order status transitions, estimate
  transitions/conversion, and billing mutations.
- Django admin remains separate from shop-facing authorization.
- Some admin workflows already route through services, especially repair-order
  status transitions.
- Billing and estimate admin still save directly in places.
- The app is still local-development only and not production-ready.

## Decision

Django admin is an emergency/development back-office console for now.

Trusted superusers/staff may use it for inspection, repair, setup, development
support, and emergency correction. It is not the normal shop operation,
technician/front-desk workflow, routine billing workflow, or production
customer-data workflow.

When a domain service exists and a future admin action mutates business state,
admin work should prefer calling that service. Any future production bypass must
require an explicit override reason and audit trail.

Full object-policy enforcement inside Django admin is deferred.

## Consequences

Positive:

- The project has an explicit boundary instead of ambiguous admin behavior.
- Future slices can distinguish shop-facing permissions from emergency admin
  behavior.
- Production hardening has a clearer checklist item.

Negative:

- Admin remains more powerful than the shop-facing UI.
- Admin can still bypass some object policies.
- Some admin saves still do not call services.

Follow-up:

- Admin service-alignment pass
- Admin override/audit reason model
- Admin object-policy enforcement or production restriction
- Production deployment checklist update
