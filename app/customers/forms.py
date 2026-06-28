from django import forms

from .models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "first_name",
            "last_name",
            "business_name",
            "phone_primary",
            "phone_secondary",
            "email",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
    # Individual/business name validation is handled by Customer.clean(), which
    # Django's ModelForm calls automatically via _post_clean() -> instance.full_clean().
