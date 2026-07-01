# 0050: Bootstrap UI Foundation

## Status

Accepted.

## Context

Unicos is a server-rendered Django monolith with no frontend build tooling. The
existing UI was implemented with project CSS only, which worked for early
slices but made common navigation, alerts, buttons, tables, and responsive
behavior more expensive to keep consistent.

The app needs a lightweight, local UI foundation before more shop-facing
workflow screens are added.

## Decision

Use Bootstrap 5.3 as the baseline UI framework by vendoring Bootstrap CSS and
JavaScript under Django static files.

Bootstrap is loaded from local static assets before `app/static/css/unicos.css`.
The project stylesheet remains the domain-specific override layer for repair
order statuses, operational cards, forms, print views, HTMX fragments, and
shop-specific utilities.

No frontend build tooling, SPA framework, or Tailwind runtime is introduced.

## Rationale

- Bootstrap gives the project stable, familiar primitives for layout,
  navigation, alerts, buttons, cards, tables, responsive behavior, and simple
  JavaScript interactions.
- Vendoring the assets avoids a runtime CDN dependency for core UI behavior.
- Keeping `unicos.css` as the override layer preserves existing domain styling
  and print-specific behavior.
- This fits the server-rendered Django architecture and keeps the implementation
  narrow.

## Consequences

- Future templates should prefer Bootstrap primitives for common UI controls.
- Domain-specific styles should stay in `unicos.css`.
- Bootstrap JavaScript is available for simple components such as navbar
  collapse, but complex client behavior should still be justified slice by
  slice.
- Bootstrap Icons are not included in this slice.
