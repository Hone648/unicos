# 0013: HTMX Status Updates

Status: Accepted

Decision:

Introduce HTMX for targeted repair-order status updates, replacing the full-page
POST/redirect cycle with a partial DOM update on the detail page.

**HTMX is introduced only for the status update interaction**

No other views, forms, or pages use HTMX in this slice. The scope is deliberately
minimal — one form, one interaction — so the team can evaluate HTMX in production
before committing to broader adoption.

**Normal server-rendered POST/redirect behavior remains as fallback**

The status update view checks for the `HX-Request` header to detect HTMX
requests. If the header is absent (JavaScript disabled, non-HTMX client, curl),
the view follows the original redirect-after-POST pattern unchanged.

```python
is_htmx = request.headers.get("HX-Request") == "true"
if not is_htmx:
    return redirect("repair_orders:detail", pk=pk)
```

This means the form continues to work in any browser with JavaScript disabled.

**No API endpoint is added**

The HTMX view returns partial HTML (Django templates), not JSON. No REST or
GraphQL API is introduced. The same Django template rendering pipeline is used
for both full-page and partial responses.

**No frontend build tooling is added**

HTMX is loaded via a single pinned CDN script tag in `base.html`:

```html
<script src="https://unpkg.com/htmx.org@2.0.4" defer></script>
```

No npm, Node, Vite, webpack, or PostCSS is involved. The pinned version (2.0.4)
ensures reproducible behavior without a build step.

**Status updates still go through `RepairOrder.set_status()`**

The HTMX response path calls `ro.set_status(new_status, changed_by=request.user,
note=...)` exactly as the redirect path did. Status history is preserved with
the correct `changed_by` user. Same-status and invalid-status guards are also
preserved in both paths.

**HTMX is intentionally scoped to the smallest interaction first**

The pattern used here (OOB swaps for badge, messages, history; main swap for
the form card) can be replicated for other interactions later. Starting small
allows the team to discover any integration friction (CSRF, partial template
structure, test patterns) before scaling HTMX usage.

**OOB swap targets**

The HTMX response (`_status_update_response.html`) updates four regions:

| Target ID             | Mechanism  | Content                        |
|-----------------------|------------|--------------------------------|
| `#status-update-card` | main swap  | refreshed status form          |
| `#messages`           | OOB swap   | flash messages                 |
| `#ro-status-badge`    | OOB swap   | updated status badge in header |
| `#status-history-card`| OOB swap   | updated status history table   |

The `#messages` div is always rendered in `base.html` (even when empty) so
HTMX can find the OOB target reliably.

**CSRF**

No special CSRF configuration is required. HTMX submits the form's
`csrfmiddlewaretoken` hidden input (injected by `{% csrf_token %}`) as part of
the POST body, which Django's CSRF middleware accepts.

**Deferred scope**

- HTMX on search/filter inputs (live search)
- HTMX on invoice/payment UI
- HTMX on status changes from the list view
- HTMX on customer/vehicle sections of the detail page
- WebSocket or SSE for multi-user real-time updates
- Tailwind CSS
- Custom JavaScript beyond HTMX loading
