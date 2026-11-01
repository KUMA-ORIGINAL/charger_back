"""Описание полей модели для фронта и приведение значений к JSON.

Фронт не знает моделей: какой виджет рисовать и как показать значение, он
узнаёт из ``type`` поля. Список типов закрыт — новый тип нужно поддержать и в
``admin-ui/src/features/resources/fields``.
"""

import datetime
import decimal

from django.db import models
from django.db.models.fields.files import FieldFile
from django.utils.text import capfirst
from phonenumber_field.modelfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber

FIELD_TYPES = (
    "string", "text", "integer", "decimal", "number", "boolean", "date", "datetime",
    "time", "choice", "fk", "m2m", "image", "file", "json", "email", "url", "phone",
    # Только через ``widgets``/``extra_fields`` ресурса: из модели не выводятся.
    "multichoice", "password",
)


def model_field_type(field):
    if getattr(field, "choices", None):
        return "choice"
    if isinstance(field, models.ManyToManyField):
        return "m2m"
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return "fk"
    if isinstance(field, models.BooleanField):
        return "boolean"
    if isinstance(field, (models.AutoField, models.IntegerField)):
        return "integer"
    if isinstance(field, models.DecimalField):
        return "decimal"
    if isinstance(field, models.FloatField):
        return "number"
    if isinstance(field, models.DateTimeField):
        return "datetime"
    if isinstance(field, models.DateField):
        return "date"
    if isinstance(field, models.TimeField):
        return "time"
    if isinstance(field, models.ImageField):
        return "image"
    if isinstance(field, models.FileField):
        return "file"
    if isinstance(field, models.JSONField):
        return "json"
    if isinstance(field, PhoneNumberField):
        return "phone"
    if isinstance(field, models.EmailField):
        return "email"
    if isinstance(field, models.URLField):
        return "url"
    if isinstance(field, models.TextField):
        return "text"
    return "string"


def describe_model_field(field, site=None):
    kind = model_field_type(field)
    info = {
        "name": field.name,
        "label": capfirst(str(field.verbose_name)),
        "type": kind,
        "help_text": str(field.help_text or ""),
        "required": _is_required(field),
        "read_only": not field.editable or isinstance(field, models.AutoField),
    }
    if kind == "choice":
        info["choices"] = [{"value": value, "label": str(label)} for value, label in field.flatchoices]
    if kind in ("fk", "m2m"):
        target = site.resource_for_model(field.related_model) if site else None
        info["related_resource"] = target.key if target else None
    if kind == "decimal":
        info["decimal_places"] = field.decimal_places
    if kind == "string" and field.max_length:
        info["max_length"] = field.max_length
    # Значение по умолчанию — чтобы форма создания начиналась с него, а не с
    # пустоты (иначе новая скидка или сотрудник создавались бы выключенными).
    # Вычисляемые умолчания (timezone.now) остаются бэкенду.
    if field.has_default() and not callable(field.default) and kind not in ("fk", "m2m", "image", "file"):
        info["default"] = plain(field.default)
    return info


def _is_required(field):
    if field.blank:
        return False
    if field.has_default() or isinstance(field, models.AutoField):
        return False
    if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
        return False
    return True


def related_label(obj):
    """Подпись связанного объекта: ресурс модели может задать её короче ``__str__``."""
    from .site import staff_site

    resource = staff_site.resource_for_model(type(obj))
    return resource.label_for(obj) if resource is not None else str(obj)


def plain(value):
    """Значение поля как JSON: связь — ``{id, label}``, файл — URL, деньги — число."""
    if value is None:
        return None
    if isinstance(value, models.Model):
        return {"id": value.pk, "label": related_label(value)}
    if isinstance(value, models.Manager):
        return [plain(item) for item in value.all()]
    if isinstance(value, FieldFile):
        return value.url if value else None
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, PhoneNumber):
        return str(value)
    return value
