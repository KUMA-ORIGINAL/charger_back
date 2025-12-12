from django.conf import settings
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += [
        path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    ]
