# 0028: Readiness Roadmap And Documentation

Status: Accepted

Decision:

Refresh project documentation so it reflects the real implemented state of the
app and clearly records the main readiness gaps before the next major feature
expansion.

Rationale:

- The README was stale relative to implementation and still framed the project
  as an accounts/auth baseline.
- The README now reflects actual app capabilities including dashboard workflow
  visibility, customer/vehicle management, repair-order workflows, billing,
  printable invoices, generated document numbers, invoice queue, and hardened
  CI.
- Production readiness is explicitly not complete.
- Authorization and lifecycle centralization are the next architectural risks.
- Missing body-shop workflow areas are now documented.
- Pagination, validation, and quality gates are tracked as roadmap items.

Scope:

- Documentation-only change.
- No runtime behavior changed.
- No code, model, migration, settings, Docker, CI, auth, permission,
  pagination, service-layer, production deployment, lint, format, type, or
  coverage implementation was added.
