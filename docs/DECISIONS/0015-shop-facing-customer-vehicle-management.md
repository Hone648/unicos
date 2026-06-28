# 0015: Shop-Facing Customer and Vehicle Management

Status: Accepted

Decision:

Add shop-facing create, edit, list, and detail views for customers and vehicles,
allowing staff to manage customer and vehicle records from the shop workspace
without needing Django admin.

**Customer and vehicle management is added as a first-class workspace feature**

Staff can now create and edit customers and vehicles directly from the shop UI.
Previously, these records could only be created through Django admin, which
blocked the repair-order create/edit flow whenever a customer or vehicle did
not yet exist.

**Vehicle creation is scoped to a specific customer via URL**

Vehicles are always created under a known customer. The route
`/customers/<pk>/vehicles/new/` receives the customer pk from the URL; the view
sets `vehicle.customer` from the URL rather than exposing a customer selector in
the form. This eliminates the risk of assigning a vehicle to the wrong customer
through the form.

**Vehicle editing does not expose the customer field**

`VehicleForm` excludes `customer`. The edit view loads the existing instance,
so the customer FK is preserved automatically without user input. This prevents
reassignment of a vehicle to a different customer from the shop UI.

**Customer identity validation remains in the model**

`Customer.clean()` validates that an individual has at least a first or last
name, and that a business has a business name. `CustomerForm` does not duplicate
this logic; Django's `ModelForm._post_clean()` calls `instance.full_clean()`
which calls `model.clean()` automatically.

**VIN normalization remains in the model**

`Vehicle.clean_fields()` normalizes the VIN (strip + uppercase) before the VIN
regex validator runs. `VehicleForm` does not duplicate this; normalization and
validation both happen through `ModelForm._post_clean()`.

**Vehicle creation lives in `vehicles/views.py` and is imported into `customers/urls.py`**

The `vehicle_create_for_customer` view is a vehicle operation, so it lives with
other vehicle views. The URL is mounted under the customers namespace
(`customers:vehicle_create`) because the route is nested under a customer pk.
This keeps the view logic with vehicles while the URL hierarchy reflects the
parent-child relationship.

**No deletions, no deactivation flows, no duplicate-merge**

Deactivation is supported only via the `is_active` checkbox in the edit form.
Hard delete, merge, and transfer flows are deferred to a future slice.

**No dynamic vehicle filtering by customer**

The repair-order create/edit form does not filter the vehicle dropdown by the
selected customer. Staff must navigate to the customer workspace to find or
create the correct vehicle, then return to the repair order form. Dynamic
filtering would require JavaScript; this slice deliberately excludes JavaScript
beyond HTMX.

**Out of scope for this slice**

- Customer deletion or merging
- Vehicle transfer to a different customer
- Search/filter on the vehicle list (vehicles are accessed via their customer)
- Parts, estimates, photos, or insurance workflows
- Dynamic vehicle/customer filtering in the repair order form
