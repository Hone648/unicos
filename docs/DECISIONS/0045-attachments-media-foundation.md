# 0045 — Attachments / Media Foundation

## Status

Accepted

## Update

Slice 45 added local Docker media persistence, media health checking, and
attachment validation hardening. See
`0047-local-media-persistence.md`.

## Context

Repair orders need associated files: photos of damage, signed estimates, authorization
forms, invoices, and supplemental documents. The app had no mechanism to attach files
to repair orders.

The app is still local-development only. Production media serving, storage, and security
have not been designed. The existing repair-order object policies can scope attachment
access without introducing new permission primitives.

## Decision

Add an `attachments` app with an `Attachment` model linked to `RepairOrder`. Use Django
`FileField` with local `MEDIA_ROOT` (the `media/` directory in the repo root, already
in `.gitignore` and `.dockerignore`). Serve media through Django only in `DEBUG` mode
(development-only `static()` serving).

Gate upload, download, and delete through existing app permissions and repair-order
object policy:

- **Upload**: requires `repair_orders.manage` (Owner/Admin, Manager, Front Desk) and
  `can_view_repair_order`. Technicians cannot upload.
- **Download**: requires `repair_orders.view` and `can_view_repair_order`. Technicians
  can only download attachments for their assigned repair orders.
- **Delete**: restricted to Owner/Admin/Manager and superusers. Front Desk can upload
  but cannot delete — removing evidence/photos is more sensitive than uploading.

File validation is extension-only (jpg, jpeg, png, gif, webp, pdf, txt, csv; max 25 MB).
No external content sniffing dependency is added.

Keep cloud storage, malware scanning, image processing, and customer portal uploads out
of this slice.

## Consequences

**Positive:**

- Operators can associate files and photos with repair orders through the shop-facing UI.
- Attachment access inherits the existing repair-order visibility model.
- Upload filename is stored in `original_filename`; actual stored path uses a UUID prefix
  to prevent collisions and path traversal. The original filename is restored on download.
- Local media behavior is explicit and testable with `override_settings(MEDIA_ROOT=...)`.

**Trade-offs:**

- Local filesystem storage is not production-ready. Media files are not served privately,
  backed up, or access-logged in this slice.
- File validation is basic. Extension mismatch is not caught (e.g. a renamed `.exe`).
- `media/` is excluded from git and Docker build context. Files are local to the running
  container and are lost on container recreation without a volume mount.
- Backups, private media serving, access logging, and malware scanning remain future work.

## Future work

- Mount a named Docker volume or bind mount for `media/` so files survive container
  restarts in local development.
- Move to object storage (S3-compatible) for production.
- Add content-type sniffing (e.g. python-magic) for more robust validation.
- Add malware scanning integration.
- Add private media serving (X-Accel-Redirect for nginx or presigned URLs for S3).
- Extend attachment scoping to estimates, invoices, or a global attachment queue.
