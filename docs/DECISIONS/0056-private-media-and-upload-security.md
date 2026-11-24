# 0056. Private media and upload security

## Status

Proposed.

## Current behavior

Repair-order attachments use local Django file storage. Development Compose
persists them in a named volume under
[ADR 0047](0047-local-media-persistence.md).
The shop-facing download view checks repair-order visibility and streams the
file via Django. Existing policies also govern upload and deletion. Preserve
those role and object checks, including the Technician assigned-order scope.

## Proposal

Keep beta media in persistent storage outside the public web root, with
filesystem access limited to the required service accounts. Serve downloads
only through a request authorized for the associated repair order. Keep the
media mount private to the services that require it and ensure direct URL
requests cannot serve files. Include media in the matching database recovery
set under [ADR 0055](0055-local-backup-and-recovery.md).

Keep the current file size, extension, filename, and content checks. Add
malware screening with quarantine before download availability. Keep
unscanned or suspect uploads unavailable if the scanner is down. Protect scan
logs and avoid sending customer documents to third-party scanning services.
See [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

## Acceptance and open choices

Verify allowed and denied downloads, direct URL denial, persistence across
container recreation, scanner failure, quarantine, and safe recovery with test
files. Storage layout, scanner and update strategy, upload workflow, and
quarantine retention and disposition remain open.
