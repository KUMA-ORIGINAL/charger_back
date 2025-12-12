from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins

from ..models import QAEntry
from ..serializers import QAEntrySerializer


@extend_schema(
    parameters=[
        OpenApiParameter(
            name='type',
            type=str,
            location=OpenApiParameter.QUERY,
            description='Фильтрация по типу (osago, nc, vzr, faq)'
        )
    ]
)
class QAEntryViewSet(viewsets.GenericViewSet,
                     mixins.ListModelMixin,):
    """
    Получить список вопросов и ответов по категориям (ОСАГО, НС, ВЗР, FAQ).
    """
    serializer_class = QAEntrySerializer
    queryset = QAEntry.objects.all().order_by('order')

    def get_queryset(self):
        queryset = super().get_queryset()
        qtype = self.request.query_params.get('type')
        if qtype:
            queryset = queryset.filter(type=qtype)
        return queryset