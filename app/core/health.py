from pathlib import Path
from uuid import uuid4

from django.conf import settings


def check_media_storage():
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    probe_path = media_root / f".healthz-{uuid4().hex}.tmp"
    probe_path.write_text("ok", encoding="utf-8")
    probe_path.unlink()
