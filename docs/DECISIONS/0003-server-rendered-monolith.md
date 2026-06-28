# 0003: Server-Rendered Monolith

Status: Accepted

Decision:

Start as a server-rendered Django monolith.

Rationale:

- A monolith keeps early development simple and coherent.
- Server-rendered Django fits CRUD-heavy operational workflows.
- One deployable app is easier to run on a local network.
- Shared domain logic, templates, forms, and admin workflows can evolve together.

React or another SPA layer can be added later only if justified by workflow
complexity.
