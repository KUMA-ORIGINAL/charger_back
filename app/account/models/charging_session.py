from decimal import Decimal

from django.db import models

from common.base_model import BaseModel


class ChargingSession(BaseModel):
    """Сессия зарядки с биллингом и логированием"""
    STATUS_CHOICES = [
        ('preparing', 'Подготовка'),
        ('charging', 'Зарядка'),
        ('stopped', 'Остановлена'),
        ('completed', 'Завершена'),
        ('error', 'Ошибка'),
    ]

    charge_point = models.ForeignKey(
        'ChargePoint',
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    transaction_id = models.IntegerField(null=True, blank=True, db_index=True)
    connector_id = models.IntegerField(default=1)
    id_tag = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='preparing',
        db_index=True
    )

    # Биллинг
    initial_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Начальный баланс в сомах"
    )
    consumed_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Потреблено кВт⋅ч"
    )
    cost_per_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('12.00'),
        help_text="Стоимость за 1 кВт⋅ч"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Общая стоимость"
    )

    # Метрика
    start_meter_value = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Показание счетчика при старте (Wh)"
    )
    last_meter_value = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Последнее показание счетчика (Wh)"
    )

    # Временные метки
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'charging_sessions'
        verbose_name = 'Сессия зарядки'
        verbose_name_plural = 'Сессии зарядки'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['charge_point', 'status']),
            models.Index(fields=['transaction_id']),
        ]

    def __str__(self):
        return f"Session #{self.id} - {self.charge_point.cp_id} [{self.status}]"

    @property
    def remaining_balance(self):
        """Остаток баланса в сомах"""
        return float(self.initial_balance) - float(self.total_cost)

    @property
    def can_continue_charging(self):
        """Можно ли продолжать зарядку"""
        return self.remaining_balance > 0 and self.status == 'charging'

    def update_consumption(self, current_meter_wh):
        """
        Обновить потребление на основе показаний счетчика

        Args:
            current_meter_wh: Текущее показание в Wh
        """
        current_meter_wh = Decimal(str(current_meter_wh))

        if self.start_meter_value is None:
            self.start_meter_value = current_meter_wh
            self.last_meter_value = current_meter_wh
            return

        # Рассчитываем потребление в кВт⋅ч
        consumed_wh = current_meter_wh - self.start_meter_value
        self.consumed_kwh = consumed_wh / Decimal('1000')

        # Рассчитываем стоимость
        self.total_cost = self.consumed_kwh * self.cost_per_kwh
        self.last_meter_value = current_meter_wh