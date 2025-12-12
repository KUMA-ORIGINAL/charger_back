from rest_framework import generics, permissions

from ..models import User
from ..serializers import ReferralSerializer


class ReferralsMeListView(generics.ListAPIView):
    serializer_class = ReferralSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(inviter=self.request.user)


