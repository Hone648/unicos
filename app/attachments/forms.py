import os

from django import forms

from .models import Attachment

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
_MAX_FILENAME_LENGTH = 255

_ALLOWED_EXTENSIONS = frozenset({"csv", "gif", "jpeg", "jpg", "pdf", "png", "txt", "webp"})
_ALLOWED_CONTENT_TYPES = {
    "csv": {"text/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"},
    "gif": {"image/gif"},
    "jpeg": {"image/jpeg"},
    "jpg": {"image/jpeg"},
    "pdf": {"application/pdf"},
    "png": {"image/png"},
    "txt": {"text/plain", "application/octet-stream"},
    "webp": {"image/webp"},
}
_MAGIC_BYTES = {
    "gif": (b"GIF87a", b"GIF89a"),
    "jpeg": (b"\xff\xd8",),
    "jpg": (b"\xff\xd8",),
    "pdf": (b"%PDF",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),
}


class AttachmentForm(forms.ModelForm):
    file = forms.FileField(max_length=_MAX_FILENAME_LENGTH)

    class Meta:
        model = Attachment
        fields = ["file", "category", "description"]

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            return uploaded

        filename = _uploaded_filename(uploaded)
        if not filename:
            raise forms.ValidationError("Filename is required.")
        if len(filename) > _MAX_FILENAME_LENGTH:
            raise forms.ValidationError("Filename must not exceed 255 characters.")
        if _is_path_like(filename):
            raise forms.ValidationError("Filename must not include path separators.")

        if uploaded.size > _MAX_UPLOAD_BYTES:
            mb = uploaded.size // (1024 * 1024)
            raise forms.ValidationError(f"File size must not exceed 25 MB. This file is {mb} MB.")

        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        if ext not in _ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS))
            raise forms.ValidationError(
                f"File type '.{ext}' is not allowed. Allowed extensions: {allowed}."
            )

        content_type = (getattr(uploaded, "content_type", "") or "").lower()
        if content_type and content_type not in _ALLOWED_CONTENT_TYPES[ext]:
            raise forms.ValidationError(
                f"File content type '{content_type}' does not match '.{ext}' uploads."
            )

        if not _has_valid_magic_bytes(uploaded, ext):
            raise forms.ValidationError(f"File content does not match '.{ext}' uploads.")

        return uploaded


def _uploaded_filename(uploaded):
    return getattr(uploaded, "_name", None) or uploaded.name or ""


def _is_path_like(filename):
    return (
        "/" in filename
        or "\\" in filename
        or os.path.basename(filename) != filename
        or not filename.strip()
    )


def _has_valid_magic_bytes(uploaded, ext):
    expected_signatures = _MAGIC_BYTES.get(ext)
    if not expected_signatures:
        return True

    try:
        position = uploaded.tell()
    except (AttributeError, OSError):
        position = None

    header = uploaded.read(12)

    try:
        uploaded.seek(position or 0)
    except (AttributeError, OSError):
        pass

    if ext == "webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    return any(header.startswith(signature) for signature in expected_signatures)
