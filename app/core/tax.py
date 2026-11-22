"""Shared, deterministic tax calculation helpers.

This module intentionally has no dependency on the estimates or billing models.
It provides the money/rate quantization primitives, the combined sales-tax
calculation, and the Texas-default taxability lookup used by both apps.

Texas design assumptions (see ADR 0051):

* The combined state/local sales tax rate is configurable (``SHOP_SALES_TAX_RATE``).
* The app does not determine local tax jurisdiction automatically.
* Labor is not taxable by default.
* Parts and materials are taxable by default.
* Sublet and misc are manually configurable and default to not taxable.

None of this is tax or legal advice; it is a configurable calculation
foundation that the shop can adjust.
"""

from decimal import ROUND_HALF_UP, Decimal

# Money is rounded to cents; rates keep enough precision for combined
# state/local rates such as 0.08250.
MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.00001")

# Texas default taxability by estimate/invoice line-item type.
_DEFAULT_TAXABLE_BY_ITEM_TYPE = {
    "labor": False,
    "parts": True,
    "materials": True,
    "sublet": False,
    "misc": False,
}


def quantize_money(value):
    """Return ``value`` rounded to cents using ROUND_HALF_UP."""
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def calculate_tax(taxable_subtotal, tax_rate):
    """Return the sales tax for ``taxable_subtotal`` at ``tax_rate``.

    Both arguments are coerced to ``Decimal`` and the result is quantized to
    cents. ``calculate_tax(Decimal("100.00"), Decimal("0.0825"))`` is
    ``Decimal("8.25")``.
    """
    taxable_subtotal = Decimal(taxable_subtotal)
    tax_rate = Decimal(tax_rate)
    return quantize_money(taxable_subtotal * tax_rate)


def default_taxable_for_item_type(item_type):
    """Return the Texas default taxability for a line-item type.

    Unknown types default to ``False`` (not taxable) so unusual charges are
    never silently taxed without an explicit choice.
    """
    return _DEFAULT_TAXABLE_BY_ITEM_TYPE.get(item_type, False)


def default_sales_tax_rate():
    """Return the configured combined sales tax rate.

    Used as the field default for estimate/invoice ``tax_rate`` so each record
    snapshots the rate in effect at creation time. Imported lazily to keep the
    calculation helpers usable without Django configured.
    """
    from django.conf import settings

    return settings.SHOP_SALES_TAX_RATE
