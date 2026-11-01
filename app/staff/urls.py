from django.urls import path

from .auth import CsrfView, LoginView, LogoutView, MeView
from .dashboard import DashboardView, NavBadgesView
from .meta import MetaView
from .site import staff_site

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="staff-csrf"),
    path("auth/login/", LoginView.as_view(), name="staff-login"),
    path("auth/logout/", LogoutView.as_view(), name="staff-logout"),
    path("auth/me/", MeView.as_view(), name="staff-me"),
    path("meta/", MetaView.as_view(), name="staff-meta"),
    path("dashboard/", DashboardView.as_view(), name="staff-dashboard"),
    path("nav-badges/", NavBadgesView.as_view(), name="staff-nav-badges"),
    *staff_site.get_urls(),
]
