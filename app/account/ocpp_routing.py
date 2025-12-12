from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/ocpp/(?P<cp_id>\w+)/$', consumers.OCPPConsumer.as_asgi()),
]
