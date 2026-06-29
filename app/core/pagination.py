from django.core.paginator import Paginator

DEFAULT_PAGE_SIZE = 25


def paginate_queryset(request, queryset, *, per_page=DEFAULT_PAGE_SIZE):
    """Return a Page for the requested page number.

    Uses Paginator.get_page() which safely clamps invalid and out-of-range
    values rather than raising an exception.
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page", 1)
    return paginator.get_page(page_number)


def pagination_querystring(request):
    """Return URL-encoded query string with 'page' removed.

    Pagination links can append &page=N to the result without duplicating the
    current page number or dropping existing filters.
    """
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()
