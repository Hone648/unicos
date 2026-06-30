from accounts.authorization import (
    PERM_CUSTOMERS_MANAGE,
    PERM_CUSTOMERS_VIEW,
    app_permission_required,
)
from core.pagination import paginate_queryset, pagination_querystring
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CustomerForm
from .models import Customer


@app_permission_required(PERM_CUSTOMERS_VIEW)
def customer_list(request):
    q = request.GET.get("q", "").strip()
    qs = Customer.objects.order_by("last_name", "first_name", "business_name")
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(business_name__icontains=q)
            | Q(phone_primary__icontains=q)
            | Q(email__icontains=q)
            | Q(city__icontains=q)
        )
    page_obj = paginate_queryset(request, qs)
    return render(
        request,
        "customers/customer_list.html",
        {
            "customers": page_obj.object_list,
            "page_obj": page_obj,
            "pagination_query": pagination_querystring(request),
            "q": q,
        },
    )


@app_permission_required(PERM_CUSTOMERS_VIEW)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    vehicles = customer.vehicles.order_by("make", "model", "vin")
    repair_orders = customer.repair_orders.select_related("vehicle").order_by("-opened_at", "-id")
    return render(
        request,
        "customers/customer_detail.html",
        {
            "customer": customer,
            "vehicles": vehicles,
            "repair_orders": repair_orders,
        },
    )


@app_permission_required(PERM_CUSTOMERS_MANAGE)
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Customer {customer.display_name} created.")
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = CustomerForm()
    return render(
        request,
        "customers/customer_form.html",
        {
            "form": form,
            "mode": "create",
            "title": "New Customer",
            "submit_label": "Create Customer",
            "customer": None,
        },
    )


@app_permission_required(PERM_CUSTOMERS_MANAGE)
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Customer {customer.display_name} updated.")
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)
    return render(
        request,
        "customers/customer_form.html",
        {
            "form": form,
            "mode": "edit",
            "title": f"Edit {customer.display_name}",
            "submit_label": "Save Changes",
            "customer": customer,
        },
    )
