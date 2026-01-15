from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group

from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from ..models import User
from common.base_admin import BaseModelAdmin


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
