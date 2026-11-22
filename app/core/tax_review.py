from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

TAX_REVIEW_REQUIRED = "Review the saved tax before changing this document’s line items."
TAX_BASIS_FIELDS = ("item_type", "quantity", "unit_price", "is_taxable")


def validate_line_tax_edit(line, document, document_id_field):
    """Protect saved tax when a line is added, moved, or financially edited."""
    if document.tax_breakdown_recorded and not line.pk:
        return
    fields = (document_id_field, *TAX_BASIS_FIELDS)
    previous = type(line).objects.filter(pk=line.pk).values(*fields).first() if line.pk else None
    if previous and all(previous[field] == getattr(line, field) for field in fields):
        return
    if not document.tax_breakdown_recorded or (
        previous
        and previous[document_id_field] != document.pk
        and type(document)
        .objects.filter(pk=previous[document_id_field], tax_breakdown_recorded=False)
        .exists()
    ):
        raise ValidationError(TAX_REVIEW_REQUIRED)


class TaxReviewLineItemForm(forms.ModelForm):
    def _post_clean(self):
        super()._post_clean()
        if not self.errors:
            try:
                self.instance.validate_tax_edit()
            except ValidationError as error:
                self.add_error(None, error)


class TaxReviewForm(forms.Form):
    rate = forms.DecimalField(
        label="Sales tax rate (%)",
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        max_digits=6,
        decimal_places=3,
    )

    def __init__(self, *args, line_items, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_items = line_items
        for line in line_items:
            self.fields[f"taxable_{line.pk}"] = forms.TypedChoiceField(
                label=f"{line.description} ({line.get_item_type_display()}, ${line.line_total})",
                choices=(("", "Choose taxability"), ("yes", "Taxable"), ("no", "Not taxable")),
                coerce=lambda value: value == "yes",
            )

    def save(self, document, *, recalculate, actor):
        """Apply the confirmed rate and classifications while the document is locked."""
        for line in self.line_items:
            line.is_taxable = self.cleaned_data[f"taxable_{line.pk}"]
        if self.line_items:
            document.line_items.bulk_update(self.line_items, ["is_taxable"])
        document.tax_rate = self.cleaned_data["rate"] / Decimal("100")
        document.tax_breakdown_recorded = True
        document.updated_by = actor
        document.save(
            update_fields=["tax_rate", "tax_breakdown_recorded", "updated_by", "updated_at"]
        )
        if self.line_items:
            recalculate()
