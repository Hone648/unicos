# 0051. Texas-aware estimate and invoice tax totals

## Status

Accepted

Note: this ADR is numbered `0051` as the next contiguous decision record after
`0050`. An earlier planning note suggested `0052`; `0051` is used to avoid a gap
in the decision-record sequence.

## Context

Daniel's Paint and Body needs estimates and invoices that show a pre-tax
subtotal, a taxable subtotal, a sales tax rate, a tax amount, a grand total, and
an estimated customer responsibility. Previously estimates carried only a single
`estimated_total` and invoices carried a manually entered `tax_amount`, so tax
was neither derived from line items nor consistent between an estimate and the
invoice it converts into.

This is not tax or legal advice. The goal is a configurable, deterministic,
local calculation foundation that follows current Texas design assumptions and
can be adjusted by shop configuration.

## Decision

Add a shared, model-independent tax utility (`app/core/tax.py`) with money/rate
quantization (`ROUND_HALF_UP`), `calculate_tax(taxable_subtotal, tax_rate)`, and
a Texas default-taxability lookup by line-item type.

Make the combined sales tax rate configurable through a single setting,
`SHOP_SALES_TAX_RATE`, read from the environment. It defaults to `0.0825`
(8.25%), is normalized to a `Decimal`, must be in `[0, 1]`, and fails loudly at
startup when invalid.

Snapshot tax on both estimates and invoices:

- `Estimate` gains `tax_rate`, `taxable_subtotal`, and `tax_amount`, plus
  `total_amount` and `customer_responsibility` properties. `estimated_total`
  stays the pre-tax subtotal (not renamed in the database).
- `Invoice` gains `tax_rate` and `taxable_subtotal` alongside its existing
  `subtotal`/`tax_amount`.
- Estimate and invoice line items gain `is_taxable`, defaulting to `False` at
  the model level; forms seed the Texas default from item type.

For new documents, recalculation derives tax from taxable line items using
the saved rate. Estimate-to-invoice conversion copies the approved subtotal,
tax snapshot, rate, and line taxability without recalculating the invoice at
conversion time. For documents with an unverified breakdown, price, quantity,
item type, taxability, and line additions or removals are protected by the
saved-tax guard. The shop-facing and admin invoice forms make subtotal and tax
read-only once the invoice has line items. Invoices with manual totals continue
to accept manual tax.

Authorized staff can choose Review Tax on an unverified draft in the shop
interface. They enter a percentage rate and confirm whether each line is
taxable. The application saves the confirmed breakdown and recalculates an
itemized draft in one transaction. Normal line-item edits can resume afterward.
Reviewing a draft without line items saves the rate for future itemization and
preserves the current manual amounts. Notes, descriptions, and payment
recording remain available under the existing workflow. Issued invoices and
estimates outside draft status retain their saved, unverified breakdowns.

## Texas design assumptions

- The combined state/local rate is configurable, not state-only.
- Default combined rate is `0.0825` until verified for the shop's exact address
  through the Texas Comptroller Sales Tax Rate Locator.
- Labor is not taxable by default.
- Parts and materials are taxable by default.
- Sublet and misc are manually configurable and default to not taxable.
- Users can override taxability per line item.
- The app does not determine local tax jurisdiction automatically.
- Tax snapshots (rate and derived amounts) are stored on estimates and invoices
  for historical stability.

## Consequences

Positive:

- Estimates and invoices produce consistent, itemized, Texas-aware totals.
- Tax is derived from taxable line items on new documents. Historical
  documents retain the tax already saved.
- Converting an approved estimate preserves the rate and per-line taxability.

Trade-offs:

- Adding line items to a new manual invoice begins line-based calculation.
  The calculated tax supersedes its manual tax entry. An unverified invoice
  keeps its saved tax until staff complete draft tax review.
- The shop must still verify its exact local rate; the app will not look it up.

## Slice 49 upgrade and recovery

Use the corrected release for the upgrade and back up the database before
running `python app/manage.py migrate`. Keep the original migration records.

- **Pre-Slice 48:** The `0004` schema migrations add the tax fields with
  defaults. The published billing and estimates
  `0005_backfill_line_item_taxability` migrations now perform no operations
  in either direction. Django records each migration in the original order.
  Existing subtotal, manual invoice tax, payment records, balances, approval
  capture, and statuses keep their saved values. Existing estimates had no
  tax amount field, so they start with zero added tax.
- **Slice 48 already applied:** Django skips `0005` because the IDs are
  recorded. Both paths converge at `0006_tax_breakdown_recorded`, which adds
  a false marker to existing documents and defaults new documents to true.
  No financial or approval fields are rewritten. The original backfills did
  not record which breakdowns were inferred. Therefore the upgrade treats
  all pre-upgrade documents conservatively, including genuine Slice 48
  snapshots, and shows saved tax and totals with the breakdown unavailable.
  Existing snapshot fields and flags are retained as stored.
- **Recovery:** If the original backfill already changed amounts, restore a
  pre-Slice 48 backup into a separate database and run the corrected upgrade
  there. Compare documents by invoice or estimate number. Where legitimate
  work was recorded after the backup, reconcile against the backup, issued
  invoices, approved estimates, and payment records before restoring or
  correcting production data. Without a backup or authoritative documents,
  the old manual tax and original approved amounts cannot be reconstructed
  solely from backfilled data. Slice 49 does not repair status and balance
  discrepancies already present on those databases.
- **Rollback:** Reversing `0006` drops the marker and loses its provenance.
  Reapplying it marks all extant documents as unverified again. Reversing the
  revised `0005` is a no-op and cannot undo the original code's writes.
  Reversing `0004` removes the new snapshot columns and estimate tax amount.
  Invoice tax survives as a column, with whatever value was last stored.
  Use a verified backup for a financial rollback. Do not run the original
  Slice 48 app or its original backfill over the corrected data.

## Non-goals

- No external tax API integration and no scraping/calling the Texas Comptroller
  locator from the app.
- No shop profile/admin model in this slice; the rate is an environment setting.
- No new dependencies and no frontend build tooling.

## Future work

- Shop profile/admin configuration for tax and identity settings.
- Per-jurisdiction rate handling if the shop's needs grow beyond a single
  combined rate.
