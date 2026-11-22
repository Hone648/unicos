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

Recalculation on both models now derives the taxable subtotal from taxable line
items and the tax amount from the snapshotted rate. Estimate-to-invoice
conversion copies the estimate's `tax_rate` and each line item's `is_taxable`,
so the converted invoice's totals match the approved estimate.

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
- Tax is derived from taxable line items rather than entered by hand once line
  items exist.
- Converting an approved estimate preserves the rate and per-line taxability.

Trade-offs:

- Adding taxable line items to a manually created invoice now derives tax
  automatically; a previously hand-entered `tax_amount` is superseded once line
  items drive the totals.
- The shop must still verify its exact local rate; the app will not look it up.

## Non-goals

- No external tax API integration and no scraping/calling the Texas Comptroller
  locator from the app.
- No shop profile/admin model in this slice; the rate is an environment setting.
- No new dependencies and no frontend build tooling.

## Future work

- Shop profile/admin configuration for tax and identity settings.
- Per-jurisdiction rate handling if the shop's needs grow beyond a single
  combined rate.
