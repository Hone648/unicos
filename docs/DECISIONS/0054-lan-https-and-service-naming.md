# 0054. LAN HTTPS and service naming

## Status

Proposed. The certificate strategy is open.

## Proposal

Use Caddy as the HTTPS reverse proxy. Give staff one stable DNS name that
resolves on approved shop devices to the host's private address. Keep the
proxy LAN-only under [ADR 0052](0052-lan-beta-deployment-topology.md).
Evaluate managed desktops, phones, and tablets before choosing a certificate
strategy. Staff should have a trusted HTTPS connection on each supported
client and a way to report certificate errors.

| Certificate option | Benefits | Operational requirements |
| --- | --- | --- |
| Internal CA | Certificate issuance can stay inside the shop and under its control. | Install the root certificate on every supported client. Protect CA key material, plan rotation and trust removal, and rehearse CA recovery. |
| Shop-owned domain with DNS validation (DNS-01) | Publicly trusted certificates can simplify browser onboarding while the app stays on the LAN. | Control the domain and its authoritative DNS, support scoped DNS credentials and outbound renewal, and configure internal DNS for the private address. Publish challenge records while keeping the service LAN-only. |

DNS-01 is the candidate public-CA challenge because certificate validation
does not need inbound access to the app. Keep inbound ACME challenge routes
closed. Check renewal, expiry alerts, client trust, and the effect of an
internet outage on name resolution and renewal. If choosing a public CA,
review the service name for certificate transparency exposure. See
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

## Open choices

Select the name, DNS management and resolution design, certificate strategy,
Caddy build or DNS provider support, and trust onboarding and renewal owners.
Document the supported device set and verify successful access and denied
access at the network boundary before rollout.
