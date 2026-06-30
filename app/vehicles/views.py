from accounts.authorization import (
    PERM_CUSTOMERS_MANAGE,
    PERM_CUSTOMERS_VIEW,
    app_permission_required,
)
from customers.models import Customer
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import VehicleForm
from .models import Vehicle


@app_permission_required(PERM_CUSTOMERS_MANAGE)
def vehicle_create_for_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.customer = customer
            vehicle.save()
            messages.success(
                request,
                f"Vehicle {vehicle} added for {customer.display_name}.",
            )
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = VehicleForm()
    return render(
        request,
        "vehicles/vehicle_form.html",
        {
            "form": form,
            "mode": "create",
            "title": f"Add Vehicle for {customer.display_name}",
            "submit_label": "Add Vehicle",
            "vehicle": None,
            "customer": customer,
        },
    )


@app_permission_required(PERM_CUSTOMERS_VIEW)
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related("customer"), pk=pk)
    repair_orders = vehicle.repair_orders.select_related("customer").order_by("-opened_at", "-id")
    return render(
        request,
        "vehicles/vehicle_detail.html",
        {
            "vehicle": vehicle,
            "repair_orders": repair_orders,
        },
    )


@app_permission_required(PERM_CUSTOMERS_MANAGE)
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related("customer"), pk=pk)
    if request.method == "POST":
        form = VehicleForm(request.POST, instance=vehicle)
        if form.is_valid():
            form.save()
            messages.success(request, f"Vehicle {vehicle} updated.")
            return redirect("vehicles:detail", pk=vehicle.pk)
    else:
        form = VehicleForm(instance=vehicle)
    return render(
        request,
        "vehicles/vehicle_form.html",
        {
            "form": form,
            "mode": "edit",
            "title": f"Edit {vehicle}",
            "submit_label": "Save Changes",
            "vehicle": vehicle,
            "customer": vehicle.customer,
        },
    )
