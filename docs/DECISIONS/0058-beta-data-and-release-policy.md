# 0058. Beta data and release policy

## Status

Proposed.

## Proposal

Record the source revision, immutable image digest, migration plan, and
configuration version for each release. Take and verify a pre-change recovery
set. Pause writes for designated release operations and use documented
health and workflow checks to decide whether to reopen access.

Rehearse application rollback against a compatible schema, and rehearse
restoration of the matching database and media for changes that cannot
safely be rolled back. An older image alone cannot undo an incompatible
schema or data change. Record the owner of the recovery decision and how
post-backup writes will be accounted for.

Use synthetic data through isolated acceptance testing. Verify shop roles,
intake, estimate-to-invoice conversion, payments and closure, private
attachments, and recovery. Before handling any live data, the designated shop
owner verifies the configured sales tax rate and line-item treatment for the
actual shop jurisdiction. Test a synthetic taxable and non-taxable estimate
through approval and invoice conversion against expected totals. Document
the sign-off using the [tax configuration and checks](../../README.md#sales-tax-rate).

Approve a controlled rollout to named users with an agreed operating window,
support contacts, and a fallback workflow. Define conditions for pausing the
beta, keeping track of transactions during downtime, and reconciling those
transactions after recovery. Decide whether to continue, extend, or suspend
the beta after stabilization.

## Open choices

Staff cohort, real-data scope, deployment and rollback owners, fallback
process, sign-off authority, and exit criteria remain open. The beta does not
authorize internet exposure or a hosted release. See the
[phase gates](../SLICE_PLAN.md#lan-beta-acceptance-gates).
