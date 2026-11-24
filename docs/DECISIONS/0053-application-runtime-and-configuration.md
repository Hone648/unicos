# 0053. Application runtime and configuration

## Status

Proposed.

## Proposal

- Serve Django with Gunicorn behind the LAN reverse proxy. Build a versioned
  application image once per release and record its immutable digest and
  source revision.
- Use separate beta settings and Compose configuration. Set `DEBUG=False`,
  restrict allowed hosts and CSRF origins to the selected service name, and
  configure secure session and CSRF cookies. Trust forwarded HTTPS headers
  only from the proxy and have the proxy overwrite client-supplied values.
- Inject deployment secrets at runtime from restricted files or a managed
  secret store. Keep them out of images, source, example values, and logs.
  Document rotation and recovery with limited operator access.
- Package collected static assets with the release and serve them via the
  chosen static-serving layer. Include pinned local copies of required browser
  assets, including HTMX, so a WAN outage leaves the intake flow functional.
  Keep private media on its own authorized path.
- Back up the database and media before a schema-changing release. Run
  migrations explicitly once as a controlled release step with a dedicated
  role and the versioned image. Review the migration plan and record its
  outcome before making the release available. Give the normal application
  database role only the privileges it needs at runtime.

## Acceptance and open choices

Verify deployment settings with Django's deployment checks. Start the release
in isolation and verify HTTPS, static assets, authenticated flows, health, and
a restart without an automatic migration. Rehearse the release path with
WAN access disabled for browser devices.
See the [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

The image registry, secret delivery method, worker sizing, static-serving
layer, and migration credential handling remain open. These changes belong to
future implementation slices. The development Dockerfile uses `runserver`
and the development startup applies migrations.
