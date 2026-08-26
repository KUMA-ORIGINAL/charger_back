from django.contrib import admin
from django.utils.html import format_html

from unfold.admin import TabularInline

from account.models import ChargingSession, ChargingSessionMeterValue
from common.base_admin import BaseModelAdmin


class ChargingSessionMeterValueInline(TabularInline):
    model = ChargingSessionMeterValue
    extra = 0
    can_delete = False
    max_num = 0
    ordering = ('-sampled_at',)
    fields = (
        'sampled_at', 'consumed_kwh', 'energy_wh',
        'power_kw', 'soc', 'voltage', 'current',
    )
    readonly_fields = fields
    verbose_name = 'Замер'
    verbose_name_plural = 'История замеров (MeterValues)'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChargingSession)
class ChargingSessionAdmin(BaseModelAdmin):
    inlines = [ChargingSessionMeterValueInline]

    list_display = [
        'id', 'charge_point', 'owner', 'status', 'started_at',
        'duration', 'consumed_kwh', 'soc_progress', 'power',
        'money', 'detail_link',
    ]
    list_filter = ['source', 'status', 'csms_name', 'charge_point']
    search_fields = ['id_tag', 'transaction_id', 'csms_transaction_id']
    date_hierarchy = 'started_at'
    list_select_related = ['charge_point']

    readonly_fields = [
        'duration', 'soc_progress', 'power', 'money',
        'average_power', 'consumed_kwh', 'total_cost',
        'last_meter_at', 'created_at', 'updated_at',
    ]

    fieldsets = (
        ('Станция и транзакция', {
            'fields': (
                'charge_point', 'source', 'csms_name', 'status',
                'transaction_id', 'csms_transaction_id',
                'connector_id', 'id_tag',
            )
        }),
        ('Время', {
            'fields': (
                'started_at', 'stopped_at', 'duration',
                'last_meter_at', 'stop_reason',
            )
        }),
        ('Энергия', {
            'fields': (
                'start_meter_value', 'last_meter_value', 'stop_meter_value',
                'consumed_kwh', 'power', 'average_power',
                'last_voltage', 'last_current',
            )
        }),
        ('Заряд батареи', {
            'fields': ('start_soc', 'last_soc', 'soc_progress')
        }),
        ('Биллинг', {
            'fields': (
                'initial_balance', 'cost_per_kwh', 'total_cost', 'money',
            )
        }),
        ('Служебное', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.display(description='Источник', ordering='source')
    def owner(self, obj):
        return obj.owner_label

    @admin.display(description='Длительность')
    def duration(self, obj):
        if not obj.started_at:
            return '—'
        return obj.duration_display

    @admin.display(description='Заряд, %')
    def soc_progress(self, obj):
        if obj.last_soc is None:
            return '—'
        if obj.start_soc is None:
            return f"{obj.last_soc}%"
        gain = f"{obj.soc_gain or 0:+.0f}"
        return format_html(
            '{}% → {}% <b>({})</b>', obj.start_soc, obj.last_soc, gain
        )

    @admin.display(description='Мощность')
    def power(self, obj):
        if obj.last_power_kw is None:
            return '—'
        max_kw = obj.max_power_kw
        if max_kw is None:
            return f"{obj.last_power_kw} кВт"
        return f"{obj.last_power_kw} кВт (макс. {max_kw})"

    @admin.display(description='Средняя мощность')
    def average_power(self, obj):
        return f"{obj.average_power_kw:.2f} кВт"

    @admin.display(description='Оплата')
    def money(self, obj):
        if obj.is_external:
            return '—'
        return f"{obj.total_cost} / {obj.initial_balance} сом " \
               f"(остаток {obj.remaining_balance:.2f})"
