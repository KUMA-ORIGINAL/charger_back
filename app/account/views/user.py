from django.shortcuts import redirect
from rest_framework import generics, permissions
from django.contrib.auth import get_user_model

from ..serializers import UserSerializer, UserUpdateSerializer, UserNameSerializer

User = get_user_model()


class UserMeAPIView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.request.method in permissions.SAFE_METHODS:
            return UserSerializer
        return UserUpdateSerializer

    def get_object(self):
        return self.request.user


class UserNameByIdAPIView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserNameSerializer


def short_referral_redirect(request, ref_id):
    """
    Редирект с короткой ссылки на страницу авторизации с реферальным ID.
    """
    target_url = f"https://oa.kg/a/auth/{ref_id}"
    return redirect(target_url)
