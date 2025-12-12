from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, mixins
from rest_framework.response import Response

from ..models import PageText, PageTextGlobalVersion
from ..serializers import PageTextListResponseSerializer, PageTextSerializer


class PageTextViewSet(viewsets.GenericViewSet,
                      mixins.ListModelMixin,):
    queryset = PageText.objects.all()
    serializer_class = PageTextSerializer

    @extend_schema(
        responses={200: PageTextListResponseSerializer}  # Только для OpenAPI схемы!
    )
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        version = PageTextGlobalVersion.current()
        return Response({
            "version": version,
            "results": serializer.data
        })
