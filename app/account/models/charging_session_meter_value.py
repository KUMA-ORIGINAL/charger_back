from decimal import Decimal, InvalidOperation

from django.db import models

from common.base_model import BaseModel


class ChargingSessionMeterValue(BaseModel):
    """
    Снимок телеметрии (один кадр MeterValues) внутри сессии зарядки.

    Хранится для истории: график мощности, роста заряда батареи и
    показаний счётчика по ходу зарядки.
    """

    session = models.ForeignKey(
        'ChargingSession',
        on_delete=models.CASCADE,
        related_name='meter_values',
        verbose_name='Сессия',
    )
    sampled_at = models.DateTimeField(
        db_index=True,
        verbose_name='Время замера',
    )

    energy_wh = models.DecimalField(
        max_digits=15, decimal_places=3, null=True, blank=True,
        verbose_name='Счётчик, Wh',
    )
    consumed_kwh = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True,
        verbose_name='Потреблено на момент замера, кВт⋅ч',
    )
    power_kw = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True,
        verbose_name='Мощность, кВт',
    )
    soc = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True,
        verbose_name='Заряд батареи, %',
    )
    voltage = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Напряжение, В',
    )
    current = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        verbose_name='Ток, А',
    )
    temperature = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name='Температура, °C',
    )
    raw = models.JSONField(
        default=list, blank=True,
        verbose_name='Исходные sampledValue',
    )

    class Meta:
        verbose_name = 'Замер сессии'
        verbose_name_plural = 'Замеры сессии'
        ordering = ['-sampled_at']
        indexes = [
            models.Index(fields=['session', 'sampled_at']),
        ]

    def __str__(self):
        return f"MV s={self.session_id} @{self.sampled_at:%Y-%m-%d %H:%M:%S}"

    # ------------------------------------------------------------------
    #  Разбор OCPP MeterValues
    # ------------------------------------------------------------------

    #  measurand → (поле, множитель к базовой единице)
    MEASURAND_MAP = {
        'Energy.Active.Import.Register': 'energy_wh',
        'Power.Active.Import': 'power_kw',
        'SoC': 'soc',
        'Voltage': 'voltage',
        'Current.Import': 'current',
        'Temperature': 'temperature',
    }

    @staticmethod
    def _to_decimal(value):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @classmethod
    def parse_sampled_values(cls, sampled_values: list) -> dict:
        """
        Свести список sampledValue одного кадра MeterValues к плоскому dict.

        Единицы приводятся к базовым: энергия — Wh, мощность — кВт.
        Ключ 'energy_wh' используется биллингом, поэтому имя поля совпадает
        с именем в ChargingSession.apply_meter_sample.
        """
        parsed: dict = {}

        for sv in sampled_values or []:
            if not isinstance(sv, dict):
                continue

            measurand = sv.get('measurand') or 'Energy.Active.Import.Register'
            field = cls.MEASURAND_MAP.get(measurand)
            if not field:
                continue

            value = cls._to_decimal(sv.get('value'))
            if value is None:
                continue

            unit = (sv.get('unit') or '').lower()

            if field == 'energy_wh' and unit == 'kwh':
                value = value * Decimal('1000')
            elif field == 'power_kw' and unit in ('w', ''):
                # OCPP по умолчанию отдаёт мощность в ваттах
                value = value / Decimal('1000')

            parsed[field] = value

        return parsed
