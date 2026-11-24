# 0055. Local backup and recovery

## Status

Accepted constraints. Recovery design proposed.

## Accepted constraints

An external NVMe drive is available for local backups. The initial beta will
have no off-site backup.

## Proposed recovery design

Create a recoverable set on the NVMe that pairs a PostgreSQL logical backup
with the matching private media. Quiesce application writes during capture
or establish another tested consistency mechanism. Record the source release
and database version, backup time, and integrity manifest. Include or keep
separately protected the configuration and recovery material needed to start
the matching release, decrypt backups, and restore service trust.

Encrypt backups and protect access to the drive. Keep recovery keys available
to authorized operators when the primary host is unavailable. Verify the
integrity and readability of each completed set. Exercise restoration on an
isolated target before real data is used and after material changes to the
procedure. Record elapsed time and data-loss window. Verify database records,
private attachments and their authorization, and essential shop workflows
against the restored release.
See [PostgreSQL 16 backup and restore documentation](https://www.postgresql.org/docs/16/backup-dump.html).

## Open choices

Agree on recovery point objective (RPO, tolerable data loss), recovery time
objective (RTO, tolerable downtime), backup schedule, retention, drive handling
and custody (including when it is connected), key custody, and primary and
backup recovery owners. Agree on a temporary shop workflow during outages.
Require evidence from a restore rehearsal before signing off on real data.

## Single-site risk

The host and backup can be lost together to fire, theft, flood, or other
site-wide damage. A continuously connected drive can also share exposure to
ransomware or accidental deletion. Local backups reduce the impact of some
host failures. Loss of the site can still cause permanent data loss. The shop
must acknowledge this residual risk before live use and revisit off-site
recovery before broader rollout.
