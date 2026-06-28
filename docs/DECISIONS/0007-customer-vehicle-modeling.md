# 0007: Customer and Vehicle Modeling

Status: Accepted

Decision:

Introduce `customers.Customer` and `vehicles.Vehicle` as the first body-shop
domain models, establishing the relational foundation for future repair-order
and billing work.

Key choices:

**Customer types**
- A customer is either an `individual` (person) or a `business`.
- Individual customers need at least a first name or last name (validated at
  the model layer via `clean()`).
- Business customers need a `business_name`.
- Both types share contact and address fields.

**One customer, many vehicles**
- `Vehicle` has a `ForeignKey` to `Customer` with `on_delete=PROTECT`.
- A customer can own many vehicles; each vehicle currently belongs to exactly
  one customer.
- `PROTECT` prevents casual deletion of a customer who has vehicles attached,
  which preserves business history without needing a separate archive step.

**Ownership history deferred**
- There is no ownership-history table in this slice.
- If a vehicle changes hands, the customer FK can be updated manually.
- A proper ownership-history model can be added later if the shop needs it.

**VIN rules**
- VIN is stored as uppercase (normalized in `Vehicle.save()`).
- Surrounding whitespace is stripped on save.
- VIN must be exactly 17 characters, using only `A-Z` (excluding `I`, `O`, `Q`)
  and `0-9`. Regex: `^[A-HJ-NPR-Z0-9]{17}$`.
- VIN is unique at the database level and indexed for search.
- No VIN-decode API integration yet; the field is a plain string store.

**Soft deletes via `is_active`**
- Both models have `is_active` (default `True`).
- Hard deletes of vehicles are prevented by the customer FK `PROTECT`.
- Deactivation via `is_active=False` is the intended path for retiring records.

**No domain permissions yet**
- Group/permission assignment for these models is deferred until there is a
  custom UI that needs access control.
