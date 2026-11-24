# 0057. Administrative security and operations

## Status

Proposed.

## Proposal

- Give staff named accounts with the existing least-privilege shop roles.
  Restrict Django admin to designated operators on an approved administration
  path. Keep admin mutations within the existing workflow policies.
- Limit host SSH to an approved management network and named maintenance
  users. Use key-based authentication, disable root and password login, and
  test a physical console recovery path before tightening remote access.
  Limit Docker, database, media, and backup privileges to the designated
  service or operator accounts.
- Capture application, proxy, host, and privileged-operation events and
  restrict access to the logs. Avoid credentials and customer payloads in
  logs. Define retention and check that log rotation protects disk capacity.
- Monitor HTTPS and certificate expiry, health, disk space, database and
  media availability, backup completion and age, and scanner health. Route
  failures to an identified operator and verify that operator receives and
  can act on alerts.
- Write recovery procedures for host, account, secret, and certificate loss.
  Plan maintenance windows, security updates, and documented emergency
  access. Rehearse access revocation and local recovery.

## Acceptance and open choices

Demonstrate that regular shop accounts and disallowed networks cannot reach
administrative functions, that the approved maintenance path works, and that
an operator can respond to a simulated failure. Management network design,
privileged access and recovery owners, alerting tools, log retention, and
operating schedules remain open.
