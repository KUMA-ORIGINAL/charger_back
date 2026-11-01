from rest_framework.pagination import PageNumberPagination


class StaffPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_page_size(self, request):
        size = super().get_page_size(request)
        view = getattr(request, "parser_context", {}).get("view")
        if request.query_params.get(self.page_size_query_param) is None and view is not None:
            return view.resource.list_per_page
        return size
