"""Журнал изменений из React-админки — в тот же ``LogEntry``, что ведёт Django admin.

Так история объекта одна на обе админки: «История» в /admin/ показывает и
правки из панели, а раздел «Журнал действий» в панели — и правки из /admin/.
"""

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry

PANEL = "панель"


def _log(request, objects, flag, message):
    objects = list(objects)
    if not objects or not request.user.is_authenticated:
        return
    LogEntry.objects.log_actions(
        user_id=request.user.pk, queryset=objects, action_flag=flag, change_message=message,
    )


def log_addition(request, obj):
    log_additions(request, [obj])


def log_additions(request, objects):
    _log(request, objects, ADDITION, [{"added": {}}])


def log_change(request, obj, labels):
    """``labels`` — подписи изменённых полей, как их показывает форма."""
    if labels:
        _log(request, [obj], CHANGE, [{"changed": {"fields": list(labels)}}])


def log_deletion(request, obj):
    _log(request, [obj], DELETION, [{"deleted": {}}])


def log_action(request, objects, label):
    """Запуск действия (повтор чека, открыть дверь) — тоже изменение для истории."""
    _log(request, objects, CHANGE, f"Действие «{label}» ({PANEL})")
