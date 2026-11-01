"""Схема staff-API для генерации клиента фронта: ``manage.py staff_openapi --file ...``."""

from django.core.management.base import BaseCommand
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.settings import patched_settings

# Staff-API отвечает в snake_case, поэтому camelize-хук основной схемы не нужен.
STAFF_SCHEMA_SETTINGS = {
    "TITLE": "Charger Staff API",
    "DESCRIPTION": "API React-админки (admin-ui).",
    "VERSION": "1.0.0",
    "POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums"],
    "CAMELIZE_NAMES": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "FieldTypeEnum": "staff.meta.FIELD_TYPE_CHOICES",
        "FilterTypeEnum": "staff.meta.FILTER_TYPE_CHOICES",
        "ActionVariantEnum": "staff.meta.ACTION_VARIANT_CHOICES",
    },
}


class Command(BaseCommand):
    help = "Пишет OpenAPI-схему staff-API в YAML."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)

    def handle(self, *args, file, **options):
        with patched_settings(STAFF_SCHEMA_SETTINGS):
            generator = SchemaGenerator(urlconf="staff.schema_urls")
            schema = generator.get_schema(request=None, public=True)
            output = OpenApiYamlRenderer().render(schema, renderer_context={})
        with open(file, "wb") as fh:
            fh.write(output)
        self.stdout.write(self.style.SUCCESS(f"Схема записана в {file}"))
