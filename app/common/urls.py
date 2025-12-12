from django.urls import path, include
from rest_framework.routers import DefaultRouter

from common import views

router = DefaultRouter()
router.register(r'page-texts', views.PageTextViewSet, basename='page_text')
router.register(r'qa', views.QAEntryViewSet, basename='qa_entry')

urlpatterns = [
    path('', include(router.urls))
]
