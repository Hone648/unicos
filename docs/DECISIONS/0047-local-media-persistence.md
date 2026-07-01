# 0047. Local media persistence and attachment hardening

## Status

Accepted

## Context

Slice 42 introduced repair-order attachments using local Django `FileField`
storage. That was enough for early workflow testing, but local uploads needed a
clearer persistence boundary before the app accumulated more customer,
insurance, and billing evidence.

Production media storage, malware scanning, thumbnails, and private media
serving are still out of scope.

## Decision

Persist local development uploads with a Docker Compose named volume:
`media_data` mounted at `/app/media`.

Keep `MEDIA_URL` and `MEDIA_ROOT` optional environment overrides, with local
defaults of `media/` and `REPO_ROOT / "media"`.

Extend `/healthz/` to verify both database connectivity and writable media
storage. Media failure returns HTTP 503 with a useful error payload.

Harden attachment upload validation without new dependencies:

- reject blank, path-like, or overly long filenames
- keep the allowed extension set narrow
- check content type against the extension when a browser supplies it
- keep the 25 MB size limit
- check minimal binary signatures for image/PDF uploads

## Consequences

Positive:

- Local Docker uploads survive container recreation.
- `.dockerignore` still keeps `media/` out of image build context.
- Broken or unwritable media storage is visible through `/healthz/`.
- Attachment validation catches common accidental or unsafe upload mistakes
  before more sensitive business data is added.

Trade-offs:

- This is still local filesystem storage, not production storage.
- Content checks are lightweight and do not replace malware scanning.
- Attachment scope remains repair-order only.

## Future work

- Production media serving and storage design.
- Backup/restore procedures for media.
- Malware scanning.
- Thumbnails/previews if shop workflows justify them.
- Estimate-, invoice-, or customer-scoped attachments if needed.
