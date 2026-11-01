"""Выгрузка списка в Excel с теми же колонками и фильтрами, что на экране."""

from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook

EXPORT_LIMIT = 10_000


def export_xlsx(resource, request, queryset):
    names = resource.get_list_display(request)
    columns = [resource.describe_field(name) for name in names]
    serializer_class = resource.site.serializer_for(resource, request, list_only=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = resource.label_plural[:31]
    sheet.append([column["label"] for column in columns])
    # many=True: поля сериализатора строятся один раз, а не на каждую из 10 000 строк.
    rows = serializer_class(queryset[:EXPORT_LIMIT], many=True, context={"request": request}).data
    for data in rows:
        sheet.append([_cell(column, data.get(column["name"])) for column in columns])

    buffer = BytesIO()
    workbook.save(buffer)
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H-%M")
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{resource.key}_{stamp}.xlsx"'
    return response


def _cell(column, value):
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get("label", "")
    if isinstance(value, list):
        return ", ".join(_cell(column, item) for item in value)
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if column.get("choices"):
        labels = {choice["value"]: choice["label"] for choice in column["choices"]}
        return labels.get(value, value)
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
