from django.core.files.base import ContentFile
from rest_framework import serializers
from ..models import User
from ..services import crop_face


class UserIdentificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'passport_front',
            'passport_back',
            'passport_selfie',
            'inn',
            'passport_last_name',
            'passport_first_name',
            'passport_middle_name',
            'gender',
            'birth_date',
            'document_number',
            'issue_authority',
            'issue_date',
            'expiry_date',
        ]
        extra_kwargs = {
            'passport_front': {'required': True},
            'passport_back': {'required': True},
            'passport_selfie': {'required': True},
            'inn': {'required': True},
            'passport_last_name': {'required': True},
            'passport_first_name': {'required': True},
            'passport_middle_name': {'required': True},
            'gender': {'required': True},
            'birth_date': {'required': True},
            'document_number': {'required': True},
            'issue_authority': {'required': True},
            'issue_date': {'required': True},
            'expiry_date': {'required': True},
        }

    def update(self, instance, validated_data):
        instance.identification_status = 'pending'
        response = super().update(instance, validated_data)
        selfie = validated_data.get('passport_selfie')
        if selfie:
            # crop_face теперь принимает file-like (selfie)
            selfie.seek(0)  # вдруг файл уже читали
            face_file = crop_face(selfie)
            if face_file:
                filename = f"face_{instance.pk}.jpg"
                instance.selfie_face.save(filename, ContentFile(face_file.read()), save=True)
            else:
                # Лицо не найдено — не меняем selfie_face
                pass
        return response
