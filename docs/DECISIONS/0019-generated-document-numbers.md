# 0019: Generated Document Numbers

Status: Accepted

Decision:

Add system-generated repair-order and invoice numbers so staff no longer type
document numbers manually in the shop-facing UI.

**Format: `RO-YYYY-NNNNNN` and `INV-YYYY-NNNNNN`**

Repair orders get numbers like `RO-2026-000001`; invoices get numbers like
`INV-2026-000001`. Sequences reset at the start of each calendar year (using
the shop's configured time zone, `America/Chicago`). Repair-order and invoice
sequences are independent — each maintains its own counter.

**`DocumentNumberSequence` model in the `core` app**

A new model tracks the last-used sequence value per `(document_type, year)` pair.
Fields: `document_type` (TextChoices: `repair_order` / `invoice`), `year`
(PositiveSmallIntegerField), `last_value` (PositiveIntegerField, default 0),
and standard `created_at`/`updated_at` timestamps. A unique constraint on
`(document_type, year)` enforces one row per type-year combination.

**Race-safe generator using `select_for_update()` and a savepoint**

`generate_repair_order_number()` and `generate_invoice_number()` in
`core/document_numbers.py` wrap all operations in `transaction.atomic()`.
The generator fetches the sequence row with `select_for_update()`, increments
`last_value`, and saves. On first use for a given year, the row must be
created; a nested `transaction.atomic()` savepoint catches `IntegrityError`
from concurrent first-row inserts without aborting the outer transaction, then
re-fetches with `select_for_update()`.

**Initialization from existing numbers on first use**

When the sequence row for a given year/type does not yet exist, the generator
scans existing document numbers matching the generated format
(`RO-YYYY-######` or `INV-YYYY-######`) and seeds `last_value` from the
highest suffix found. This prevents collisions with pre-existing generated-style
numbers. Manually-typed numbers that do not match the six-digit-padded format
are ignored.

**Forms split into create and edit variants; number excluded from both**

`RepairOrderCreateForm` and `RepairOrderEditForm` both exclude
`repair_order_number` from `Meta.fields`. The create view calls
`generate_repair_order_number()` and sets the field on the unsaved instance
before `save()`. The edit view passes `instance=ro` to the form; Django's
ModelForm preserves all fields not in `Meta.fields` from the existing instance,
so the number is unchanged. The same pattern applies to `InvoiceCreateForm`
and `InvoiceEditForm`.

**Templates show the number as static text, not an editable input**

In create mode, the number field area shows "Generated automatically on save."
In edit mode, the existing number is displayed as a read-only `<p>` element
with the `.form-field-readonly` CSS class. Neither mode renders
`name="repair_order_number"` or `name="invoice_number"` inputs.

**Existing records are not renumbered**

The generator only assigns a number during the create flow. Existing repair
orders and invoices keep their current numbers unchanged.

**Django admin is not affected**

Admin forms are independent of shop-facing forms. Admin users can continue to
view and edit document numbers directly if needed.

**Out of scope for this slice**

- Gapless accounting-grade numbering (gaps from failed transactions are acceptable)
- Manual renumbering or custom number settings UI
- Multi-shop prefix support
- Estimate or quote numbers
- Invoice lifecycle actions (status transitions, void, etc.)
- PDF generation, email invoices, payment links, accounting export
- API endpoints
- HTMX expansion beyond existing status update
- Tailwind or any frontend build tooling
- Custom JavaScript
