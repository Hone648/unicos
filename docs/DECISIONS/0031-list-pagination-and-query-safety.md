# 0031 — List Pagination and Query Safety

## Context

Major list pages rendered full querysets without any upper bound. As the
database grows, a single request for `/repair-orders/`, `/customers/`, or
`/billing/invoices/` would fetch and render every matching row, with no
protection against slow queries or large HTML responses.

The fix should be additive: preserve existing search, filter, and authorization
behavior, handle invalid page inputs safely, and keep query parameters across
pagination links.

## Decision

### Centralized pagination helper

A small helper module (`core/pagination.py`) encapsulates Django's built-in
paginator so individual views do not repeat try/except boilerplate:

```python
def paginate_queryset(request, queryset, *, per_page=DEFAULT_PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page", 1)
    return paginator.get_page(page_number)
```

`Paginator.get_page()` safely clamps invalid values (non-integer strings,
out-of-range page numbers) without raising exceptions.

A companion helper strips `page` from the current query string so pagination
links can append `&page=N` without duplicating or discarding existing filters:

```python
def pagination_querystring(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()
```

### Fixed page size

`DEFAULT_PAGE_SIZE = 25` is a named constant. Page size is not user-configurable
in this slice; adding user-controlled page size is left as future work.

### Views updated

- `repair_orders.views.repair_order_list`
- `customers.views.customer_list`
- `billing.views.invoice_list`

Each view passes `page_obj` and `pagination_query` to the template context, and
assigns the list variable (`repair_orders`, `customers`, `invoices`) from
`page_obj.object_list` so existing template loops require no changes.

### Reusable template partial

`app/templates/partials/_pagination.html` renders previous/page-indicator/next
controls and is included at the bottom of each list template. Controls render
only when more than one page exists. Pagination links preserve existing query
parameters via `pagination_query`.

### Query parameter preservation

Status filter tabs and search forms reset to page 1 on submission (correct
behavior). Pagination links carry existing filters via `pagination_query` so
`/repair-orders/?status=in_repair&q=ford&page=2` works correctly.

### No vehicle list page

No standalone vehicle list page exists; vehicles are displayed inside customer
detail pages. No change was needed.

## Consequences

- List pages are bounded at 25 results per page.
- Invalid `page` values are handled silently (clamp to page 1 or last page).
- Existing search, filter, and authorization behavior is unchanged.
- No model fields, indexes, or migrations were added.
- No new dependencies were added.

## Remaining limitations

- No user-controlled page size.
- No sortable columns.
- No advanced search or full-text indexing.
- No object-level authorization.
- No production hardening.
- Pagination is basic server-rendered; no infinite scroll or HTMX paging.
