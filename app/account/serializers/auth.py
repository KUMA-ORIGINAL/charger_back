from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers


class PhoneNumberSerializer(serializers.Serializer):
    phone_number = PhoneNumberField()


class VerifyCodeSerializer(serializers.Serializer):
    phone_number = PhoneNumberField(max_length=20)
    code = serializers.CharField(max_length=6)
    referral_code = serializers.CharField(required=False, allow_blank=True)

    def validate_phone(self, value):
        return value
