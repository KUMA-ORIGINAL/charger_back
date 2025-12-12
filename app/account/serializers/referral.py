from rest_framework import serializers

from ..models import User


class ReferralSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'full_name',
            'phone_number',
            'date_joined',
            'osago_count',
            'osago_income',
        ]
