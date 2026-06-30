import os

from django import forms

from .models import Attachment

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

_ALLOWED_EXTENSIONS = frozenset({"csv", "gif", "jpeg", "jpg", "pdf", "png", "txt", "webp"})


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["file", "category", "description"]

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            return uploaded

        if uploaded.size > _MAX_UPLOAD_BYTES:
            mb = uploaded.size // (1024 * 1024)
            raise forms.ValidationError(f"File size must not exceed 25 MB. This file is {mb} MB.")

        ext = os.path.splitext(uploaded.name)[1].lstrip(".").lower()
        if ext not in _ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
            raise forms.ValidationError(
                f"File type '.{ext}' is not allowed. Allowed extensions: {allowed}."
            )

        return uploaded
