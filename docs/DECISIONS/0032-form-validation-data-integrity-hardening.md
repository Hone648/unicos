# 0032 — Form Validation and Data Integrity Hardening

## Context

Several form fields lacked explicit form-level validation, relying entirely on
model-level validators and `ModelForm._post_clean()` to surface errors. This
worked correctly but produced generic Django validator messages, and errors
attached as non-field errors (at the top of the form) rather than next to the
relevant field.

Three concrete gaps were identified:

1. **Vehicle year**: `year = PositiveSmallIntegerField(null=True, blank=True)` accepts
   any value from 0 to 32767. No range check existed to reject obviously invalid
   years like 1899 or 2050.

2. **Invoice line-item quantity and unit price**: model validators
   (`MinValueValidator(Decimal("0.01"))` for quantity,
   `MinValueValidator(Decimal("0.00"))` for unit price) fire during
   `_post_clean()` and produce the generic message
   "Ensure this value is greater than or equal to X." Adding form-level
   `clean_*` methods replaces these with domain-specific messages and attaches
   errors to the correct field earlier in validation.

3. **Payment amount**: `Payment.clean()` rejects amount ≤ 0 during `_post_clean()`,
   producing a non-field error. Adding `PaymentForm.clean_amount()` attaches the
   same rejection to the `amount` field specifically, so the error appears next
   to the field rather than at the top of the form.

## Decision

### VehicleForm.clean_year()

Added to `vehicles/forms.py`:

```python
def clean_year(self):
    year = self.cleaned_data.get("year")
    if year is not None:
        year_max = datetime.date.today().year + 2
        if year < 1900 or year > year_max:
            raise forms.ValidationError(
                f"Enter a year between 1900 and {year_max}."
            )
    return year
```

The lower bound 1900 excludes obviously invalid inputs (0, 1899). The upper
bound `current_year + 2` accommodates newly manufactured vehicles that shops
receive before their model year is officially released. `None` is allowed
because the model field is `null=True, blank=True`.

### InvoiceLineItemForm.clean_quantity() and clean_unit_price()

```python
def clean_quantity(self):
    quantity = self.cleaned_data.get("quantity")
    if quantity is not None and quantity <= 0:
        raise forms.ValidationError("Quantity must be greater than zero.")
    return quantity

def clean_unit_price(self):
    price = self.cleaned_data.get("unit_price")
    if price is not None and price < 0:
        raise forms.ValidationError("Unit price cannot be negative.")
    return price
```

Zero unit price is allowed (warranty or no-charge items). Zero or negative
quantity is never valid. The form-level check fires before `_post_clean()`,
so when it raises, the field is excluded from model-level validation and
the generic MinValueValidator message is not shown.

### PaymentForm.clean_amount()

```python
def clean_amount(self):
    amount = self.cleaned_data.get("amount")
    if amount is not None and amount <= 0:
        raise forms.ValidationError("Amount must be greater than zero.")
    return amount
```

`Payment.clean()` (model-level) still runs for overpayment and void-invoice
checks, which require the invoice to be set by the view. The form-level
`clean_amount()` handles the amount > 0 check independently of the invoice,
attaching the error to the `amount` field.

### No changes to templates, models, or migrations

All form templates already displayed `form.non_field_errors` and per-field
`form.<field>.errors`. No new fields were added; no migrations were needed.

## Audit findings — existing validation already in place

- `Customer.clean()`: individual/business name validation with `.strip()` ✅
- `Vehicle.clean_fields()`: VIN normalization (strip + uppercase) ✅
- `validate_vin()`: 17-character VIN format with excluded characters ✅
- `RepairOrder.clean()`: vehicle-belongs-to-customer cross-validation ✅
- `Invoice.clean()`: subtotal/tax ≥ 0 and due_date ≥ issued_at ✅
- `Payment.clean()`: amount > 0, void-invoice check, overpayment check ✅
- `InvoiceLineItem.save()`: calls `full_clean()` before writing to DB ✅

## Consequences

- Vehicle year inputs outside 1900–(current year + 2) are rejected at form
  level with a human-readable error attached to the year field.
- Line-item quantity ≤ 0 is rejected with "Quantity must be greater than
  zero." attached to the quantity field.
- Line-item unit price < 0 is rejected with "Unit price cannot be negative."
  attached to the unit_price field.
- Payment amount ≤ 0 is rejected with "Amount must be greater than zero."
  attached to the amount field.
- No model changes, no migrations, no new dependencies.
- 584 tests pass (↑ from 560 after Slice 27).

## Remaining validation gaps

- Phone number formatting/normalization
- State field normalization
- VIN check-digit validation
- Optional uniqueness policies (e.g., duplicate VINs across customers)
- Audit fields for customers/vehicles
