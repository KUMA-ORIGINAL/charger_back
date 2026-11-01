from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class StaffConfig(AppConfig):
    name = "staff"
    verbose_name = "React-админка"

    def ready(self):
        # Как admin.autodiscover(): каждое приложение регистрирует свои ресурсы в staff.py.
        autodiscover_modules("staff")
