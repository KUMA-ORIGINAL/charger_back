from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group
from django.shortcuts import redirect
from django.urls import reverse_lazy

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from unfold.decorators import action

from ..models import User, ChargePoint
from common.base_admin import BaseModelAdmin
from ..services.ocpp_commands import start_charging, stop_charging

admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(GroupAdmin, UnfoldModelAdmin):
    pass


@admin.register(User)
class UserAdmin(UserAdmin, BaseModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    model = User
    autocomplete_fields = ("groups",)
    list_filter = ("is_staff", "is_superuser", "is_active", "groups",)
    search_fields = ("phone_number",)
    ordering = ('-date_joined',)
    list_display_links = ('id', 'phone_number')


    def get_list_display(self, request):
        list_display = (
            'id',
            'phone_number',
            'first_name',
            'last_name',
            'is_active',
            'detail_link'
        )
        if request.user.is_superuser:
            pass
        return list_display


@admin.register(ChargePoint)
class ChargePointAdmin(BaseModelAdmin):
    list_display = ("cp_id", "name", 'detail_link')
    readonly_fields = ("created_at", "updated_at")

    actions_detail = ('start_charging_action', 'stop_charging_action')

    @action(
        description="▶ Start charging",
        url_path="start-charging",
    )
    def start_charging_action(
        self,
        request,
        object_id,
    ):
        """
        Action на странице объекта
        """
        cp = ChargePoint.objects.get(pk=object_id)

        start_charging(cp.cp_id)

        return redirect(
            reverse_lazy("admin:account_chargepoint_change", args=(object_id,))
        )

    @action(
        description="⛔ Stop charging",
        url_path="stop-charging",
    )
    def stop_charging_action(
            self,
            request,
            object_id,
    ):
        cp = ChargePoint.objects.get(pk=object_id)

        stop_charging(
            cp.cp_id,
            transaction_id=cp.active_transaction_id if hasattr(cp, "active_transaction_id") else 0,
        )

        return redirect(
            reverse_lazy("admin:account_chargepoint_change", args=(object_id,))
        )
