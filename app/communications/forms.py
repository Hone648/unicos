from django import forms

from .models import CommunicationEntry


class CommunicationEntryForm(forms.ModelForm):
    occurred_at = forms.DateTimeField(
        label="Communication time",
        help_text="When the communication happened.",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = CommunicationEntry
        fields = [
            "occurred_at",
            "direction",
            "channel",
            "contact_role",
            "contact_name",
            "summary",
            "next_step",
            "is_authorization_related",
        ]
        labels = {
            "is_authorization_related": "Authorization related",
            "next_step": "Next step / outcome",
        }
        help_texts = {
            "contact_name": "Required unless this is an internal note.",
            "summary": "Briefly record what was discussed or decided.",
        }
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
        }

    # repair_order, created_by, created_at, and updated_at are assigned by the
    # view/database. Model validation handles required contact-name rules.

    def clean_contact_name(self):
        return (self.cleaned_data.get("contact_name") or "").strip()

    def clean_summary(self):
        summary = self.cleaned_data.get("summary", "")
        if not summary or not summary.strip():
            raise forms.ValidationError("Summary is required.")
        return summary.strip()

    def clean_next_step(self):
        return (self.cleaned_data.get("next_step") or "").strip()
