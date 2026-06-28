# 0012: CSS-First UI Styling

Status: Accepted

Decision:

Add a plain-CSS styling layer to the existing server-rendered Django UI before
introducing any frontend build tooling or richer interaction libraries.

**Plain Django static CSS — no framework**

A single stylesheet (`app/static/css/unicos.css`) is served via Django's static
file handling (`STATIC_URL`, `STATICFILES_DIRS`, `{% load static %}`). No npm,
Node, Vite, Webpack, PostCSS, or any frontend build tool is involved.

This keeps the development environment simple: `docker compose up` is the only
command needed to run the full application, and the CSS is edited directly
without a watch/compile step.

**Tailwind is still deferred**

Tailwind CSS requires a build step (even the CDN play version is discouraged for
production). The expected benefit — utility-class styling — is not worth
introducing build tooling complexity until the UI is more settled. A custom CSS
file is faster to iterate and has zero runtime or build overhead.

**Reason: improve usability now without frontend build complexity**

The repair-order workspace (Slice 7) exposed a functional but visually raw UI.
Shop staff need readable tables, visible status badges, and usable forms before
HTMX or richer interactions are worth adding. A focused CSS pass addresses all
of that with one file and no new dependencies.

**HTMX is still deferred**

HTMX partial-page updates will be more valuable once the base UI is visually
stable and the team can identify which interactions need to feel instant
(e.g., status changes, search filtering). Introducing HTMX on top of raw HTML
would mean styling and interaction work happening simultaneously, which is harder
to review.

**The server-rendered Django template approach remains the UI baseline**

All page rendering continues to happen server-side via Django views and templates.
CSS classes target semantic HTML produced by Django templates. JavaScript is
not added in this slice.

**CSS design choices**

- System font stack for zero-weight native feel
- Dark header (`#1a2634`) for clear app/content boundary
- White content cards on a light gray body background
- Blue primary actions (`#2563eb`)
- Status badges with per-status color coding via `status-<slug>` classes
- `slugify` template filter converts `awaiting_approval` → `awaiting-approval`
  for CSS class names
- Max-width 1200px container to keep tables readable on wide screens
- Mobile-tolerant layout using flexbox and auto-fit grid columns

**Deferred scope**

- Tailwind CSS or any utility-class framework
- Frontend build tooling (Node, Vite, npm, PostCSS)
- HTMX partial updates
- Dark mode
- Custom icon set
- Responsive mobile-first overhaul
- Print stylesheet for invoices
