from django.contrib.auth import get_user_model
from django.db.models import Sum
from rest_framework import serializers


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    total_agents = serializers.SerializerMethodField()
    average_agents_income = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'phone_number',
            'passport_selfie',
            'balance',
            'withdrawn_total',
            'total_income',
            'osago_income',
            'agents_income',
            'osago_count',
            'agents_count',
            'referral_link',
            'auth_referral_link',
            'identification_status',
            'total_agents',
            'average_agents_income',
        )

    def get_total_agents(self, obj):
        return User.objects.filter(role='agent').count()

    def get_average_agents_income(self, obj):
        # Средний доход среди всех агентов
        agents = User.objects.filter(role='agent')
        total_income = agents.aggregate(total=Sum('agents_income'))['total'] or 0
        count = agents.count()
        if count == 0:
            return 0
        return str(round(total_income / count, 2))


class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'middle_name',
        )


class UserNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'phone_number']
