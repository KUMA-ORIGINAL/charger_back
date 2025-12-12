from rest_framework import serializers

from ..models import PageText


class PageTextSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageText
        fields = ('id', 'key', 'text', 'file')


class PageTextListResponseSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    results = PageTextSerializer(many=True)
