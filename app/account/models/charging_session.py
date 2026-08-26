from decimal import Decimal

from django.db import models
from django.utils import timezone

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

    SOURCE_PAYMENT = 'payment'
    SOURCE_CSMS = 'csms'
    SOURCE_CHOICES = [
        (SOURCE_PAYMENT, 'Оплата через QR'),
        (SOURCE_CSMS, 'Внешний CSMS'),
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

    # Источник сессии
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default=SOURCE_PAYMENT,
        db_index=True,
        help_text="Кто инициировал зарядку: наша оплата или внешний CSMS"
    )
    csms_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text="Имя внешнего CSMS (Charge24, Spark и т.д.)"
    )
    csms_transaction_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="transactionId на стороне внешнего CSMS"
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
    stop_meter_value = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Показание счетчика при остановке (Wh)"
    )

    # Телеметрия автомобиля / станции
    start_soc = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Заряд батареи на старте, %"
    )
    last_soc = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Последний известный заряд батареи, %"
    )
    last_power_kw = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Последняя мгновенная мощность, кВт"
    )
    max_power_kw = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Максимальная мощность за сессию, кВт"
    )
    last_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Последнее напряжение, В"
    )
    last_current = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Последний ток, А"
    )
    last_meter_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Время последнего MeterValues"
    )

    stop_reason = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text="Причина остановки (reason из StopTransaction)"
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
            models.Index(fields=['source', 'status']),
            models.Index(fields=['csms_name', 'csms_transaction_id']),
        ]

    def __str__(self):
        return f"Session #{self.id} - {self.charge_point.cp_id} [{self.status}]"

    # ------------------------------------------------------------------
    #  Свойства
    # ------------------------------------------------------------------

    @property
    def is_external(self):
        """Сессия принадлежит внешнему CSMS (Charge24, Spark и т.д.)"""
        return self.source == self.SOURCE_CSMS

    @property
    def owner_label(self):
        """Кто заряжает: имя CSMS или наша оплата"""
        if self.is_external:
            return self.csms_name or 'external'
        return 'QR оплата'

    @property
    def remaining_balance(self):
        """Остаток баланса в сомах"""
        return float(self.initial_balance) - float(self.total_cost)

    @property
    def can_continue_charging(self):
        """Можно ли продолжать зарядку"""
        return self.remaining_balance > 0 and self.status == 'charging'

    @property
    def duration_seconds(self):
        """Длительность сессии в секундах (итоговая или на текущий момент)"""
        if not self.started_at:
            return 0
        end = self.stopped_at or timezone.now()
        return max(0, int((end - self.started_at).total_seconds()))

    @property
    def duration_display(self):
        """Длительность в формате Ч:ММ:СС"""
        hours, rest = divmod(self.duration_seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    @property
    def soc_gain(self):
        """На сколько процентов зарядился автомобиль за сессию"""
        if self.start_soc is None or self.last_soc is None:
            return None
        return float(self.last_soc) - float(self.start_soc)

    @property
    def average_power_kw(self):
        """Средняя мощность за сессию, кВт"""
        seconds = self.duration_seconds
        if not seconds:
            return 0.0
        return float(self.consumed_kwh) * 3600 / seconds

    # ------------------------------------------------------------------
    #  Обновление данных
    # ------------------------------------------------------------------

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

    def apply_meter_sample(self, sample: dict, sampled_at=None):
        """
        Применить разобранные значения одного кадра MeterValues.

        Args:
            sample: dict из ChargingSessionMeterValue.parse_sampled_values
            sampled_at: время замера (по умолчанию — сейчас)
        """
        energy_wh = sample.get('energy_wh')
        if energy_wh is not None:
            self.update_consumption(energy_wh)

        soc = sample.get('soc')
        if soc is not None:
            soc = Decimal(str(soc))
            if self.start_soc is None:
                self.start_soc = soc
            self.last_soc = soc

        power_kw = sample.get('power_kw')
        if power_kw is not None:
            power_kw = Decimal(str(power_kw))
            self.last_power_kw = power_kw
            if self.max_power_kw is None or power_kw > self.max_power_kw:
                self.max_power_kw = power_kw

        voltage = sample.get('voltage')
        if voltage is not None:
            self.last_voltage = Decimal(str(voltage))

        current = sample.get('current')
        if current is not None:
            self.last_current = Decimal(str(current))

        self.last_meter_at = sampled_at or timezone.now()
