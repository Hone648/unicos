from django.test import RequestFactory, TestCase

from core.pagination import DEFAULT_PAGE_SIZE, paginate_queryset, pagination_querystring


class PaginateQuerysetTests(TestCase):
    """paginate_queryset returns correct pages and handles edge cases safely."""

    def _request(self, page=None):
        factory = RequestFactory()
        url = "/"
        if page is not None:
            url = f"/?page={page}"
        return factory.get(url)

    def _list(self, count):
        return list(range(count))

    def test_first_page_contains_page_size_items(self):
        items = self._list(DEFAULT_PAGE_SIZE + 5)
        page = paginate_queryset(self._request(), items)
        self.assertEqual(len(page.object_list), DEFAULT_PAGE_SIZE)

    def test_second_page_contains_remaining_items(self):
        items = self._list(DEFAULT_PAGE_SIZE + 5)
        page = paginate_queryset(self._request(page=2), items)
        self.assertEqual(len(page.object_list), 5)

    def test_invalid_page_string_returns_first_page(self):
        items = self._list(DEFAULT_PAGE_SIZE + 1)
        page = paginate_queryset(self._request(page="abc"), items)
        self.assertEqual(page.number, 1)

    def test_out_of_range_page_returns_last_page(self):
        items = self._list(DEFAULT_PAGE_SIZE + 1)
        page = paginate_queryset(self._request(page=999), items)
        self.assertEqual(page.number, page.paginator.num_pages)

    def test_single_page_result_has_no_other_pages(self):
        items = self._list(5)
        page = paginate_queryset(self._request(), items)
        self.assertFalse(page.has_other_pages())

    def test_empty_queryset_returns_valid_page(self):
        page = paginate_queryset(self._request(), [])
        self.assertEqual(len(page.object_list), 0)
        self.assertFalse(page.has_other_pages())

    def test_custom_per_page(self):
        items = self._list(10)
        page = paginate_queryset(self._request(), items, per_page=3)
        self.assertEqual(len(page.object_list), 3)
        self.assertEqual(page.paginator.num_pages, 4)


class PaginationQuerystringTests(TestCase):
    """pagination_querystring strips page and returns remaining params."""

    def _request(self, query_string):
        factory = RequestFactory()
        return factory.get("/", query_string)

    def test_strips_page_parameter(self):
        request = self._request({"page": "2", "q": "ford"})
        result = pagination_querystring(request)
        self.assertNotIn("page", result)
        self.assertIn("q=ford", result)

    def test_returns_empty_string_when_only_page_present(self):
        request = self._request({"page": "3"})
        result = pagination_querystring(request)
        self.assertEqual(result, "")

    def test_preserves_multiple_filters(self):
        request = self._request({"page": "2", "status": "issued", "q": "smith"})
        result = pagination_querystring(request)
        self.assertIn("status=issued", result)
        self.assertIn("q=smith", result)
        self.assertNotIn("page", result)

    def test_no_page_param_returns_all_params(self):
        request = self._request({"q": "honda", "status": "draft"})
        result = pagination_querystring(request)
        self.assertIn("q=honda", result)
        self.assertIn("status=draft", result)
