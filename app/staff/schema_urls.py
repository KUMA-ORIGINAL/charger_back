"""URLconf только со staff-API — по нему строится OpenAPI для фронта."""

from django.urls import include, path

urlpatterns = [path("api/staff/v1/", include("staff.urls"))]
