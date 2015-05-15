from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "results_per_page"
    max_page_size = 1000
