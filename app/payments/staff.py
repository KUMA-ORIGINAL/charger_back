"""QR-платежи в React-админке (``admin-ui``). Django-версия — ``payments/admin/qr_payment.py``."""

from staff.resources import StaffResource
from staff.site import staff_site

from .models import QRPayment

STATUS_BADGES = {"success": "green", "pending": "amber", "failed": "red"}


@staff_site.register(QRPayment)
class QRPaymentResource(StaffResource):
    key = "qrpayment"
    label = "QR-платёж"
    label_plural = "QR-платежи"
    group = "Сеть"
    icon = "qr-code"
    order = 35
    auto_refresh = 30
    list_tabs = "status"

    can_add = False
    can_change = False
    can_delete = False

    list_display = ("created_at", "charge_point", "amount", "status", "paid_at", "bank_id")
    list_display_links = ("created_at",)
    list_filter = ("status", "charge_point", "created_at")
    search_fields = ("bank_id", "charge_point__cp_id")
    search_help = "ID платежа в банке или станция"
    ordering = ("-created_at",)
    select_related = ("charge_point", "charging_session")
    money_fields = ("amount",)

    fieldsets = [
        ("Платёж", ("charge_point", "charging_session", "amount", "status", "paid_at", "bank_id", "link")),
        ("Служебное", ("created_at", "updated_at")),
    ]
    readonly_fields = (
        "charge_point", "charging_session", "amount", "status", "paid_at", "bank_id", "link",
        "created_at", "updated_at",
    )
    labels = {
        "created_at": "Создан", "updated_at": "Обновлён", "charge_point": "Станция",
        "charging_session": "Сессия", "amount": "Сумма", "status": "Статус", "paid_at": "Оплачен",
        "bank_id": "ID в банке", "link": "Ссылка на оплату",
    }

    def describe_field(self, name):
        info = super().describe_field(name)
        if name == "status":
            info["badges"] = STATUS_BADGES
        return info
