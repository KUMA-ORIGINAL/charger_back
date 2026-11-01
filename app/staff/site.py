"""Реестр ресурсов — аналог ``admin.site``."""

from rest_framework.routers import SimpleRouter

from . import filters
from .serializers import build_serializer


class AlreadyRegistered(Exception):
    pass


class StaffSite:
    filters = filters

    def __init__(self):
        self._registry = {}

    def register(self, model):
        def decorator(resource_class):
            if model in self._registry:
                raise AlreadyRegistered(f"{model.__name__} уже зарегистрирована в staff_site")
            resource_class.model = model
            self._registry[model] = resource_class(self)
            return resource_class

        return decorator

    @property
    def resources(self):
        return sorted(self._registry.values(), key=lambda resource: (resource.order, resource.label_plural))

    def resource_for_model(self, model):
        return self._registry.get(model)

    def get(self, key):
        return next((resource for resource in self._registry.values() if resource.key == key), None)

    def visible(self, request):
        return [resource for resource in self.resources if resource.has_perm(request, "view")]

    # Сериализатор и фильтры зависят от пользователя (поля суперпользователя,
    # выбор связей), поэтому строятся на каждый запрос — это дёшево.
    def serializer_for(self, resource, request, list_only=False):
        return build_serializer(resource, request, list_only)

    def filterset_for(self, resource, request):
        return filters.build_filterset(resource, resource.get_list_filter(request))

    def get_urls(self):
        from .views import ResourceViewSet

        router = SimpleRouter()
        for resource in self.resources:
            viewset = type(f"{resource.model.__name__}ResourceViewSet", (ResourceViewSet,), {"resource": resource})
            router.register(f"resources/{resource.key}", viewset, basename=f"staff-{resource.key}")
        return router.urls


staff_site = StaffSite()
