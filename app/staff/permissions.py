from rest_framework.permissions import BasePermission

METHOD_OPERATIONS = {
    "GET": "view",
    "HEAD": "view",
    "OPTIONS": "view",
    "POST": "add",
    "PATCH": "change",
    "PUT": "change",
    "DELETE": "delete",
}


class IsStaffMember(BasePermission):
    message = "Нужно войти как сотрудник."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class ResourcePermission(BasePermission):
    """Права Django на модель ресурса. Действия проверяют свои права сами."""

    message = "Недостаточно прав."

    def has_permission(self, request, view):
        if view.action in ("run_action", "run_bulk_action"):
            return view.resource.has_perm(request, "view")
        if view.action in ("export", "lookup"):
            return view.resource.has_perm(request, "view")
        return view.resource.has_perm(request, METHOD_OPERATIONS.get(request.method, "change"))
