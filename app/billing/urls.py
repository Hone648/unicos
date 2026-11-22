from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path(
        "repair-orders/<int:repair_order_pk>/invoice/new/",
        views.invoice_create_for_repair_order,
        name="invoice_create",
    ),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/review-tax/", views.invoice_tax_review, name="invoice_tax_review"),
    path("invoices/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("invoices/<int:pk>/issue/", views.invoice_issue, name="invoice_issue"),
    path("invoices/<int:pk>/void/", views.invoice_void, name="invoice_void"),
    path(
        "invoices/<int:invoice_pk>/payments/new/",
        views.payment_create,
        name="payment_create",
    ),
    path(
        "invoices/<int:invoice_pk>/line-items/new/",
        views.line_item_create,
        name="line_item_create",
    ),
    path(
        "line-items/<int:pk>/edit/",
        views.line_item_edit,
        name="line_item_edit",
    ),
]
