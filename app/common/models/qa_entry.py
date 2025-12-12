from django.db import models
from django.utils.translation import gettext_lazy as _


class QAEntry(models.Model):
    class QAType(models.TextChoices):
        OSAGO = 'osago', _("ОСАГО")
        NC = 'nc', _("НС")
        VZR = 'vzr', _("ВЗР")
        FAQ = 'faq', _("FAQ")

    type = models.CharField(
        max_length=10,
        choices=QAType.choices,
        verbose_name=_("Тип"),
        help_text=_("Категория вопроса: ОСАГО, НС, ВЗР, FAQ"),
        db_index=True,
    )
    question = models.CharField(
        max_length=255,
        verbose_name=_("Вопрос"),
        help_text=_("Текст вопроса")
    )
    answer = models.TextField(
        verbose_name=_("Ответ"),
        help_text=_("Текст ответа")
    )
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Порядок"),
        help_text=_("Порядок отображения")
    )

    class Meta:
        ordering = ['order']
        verbose_name = _("Вопрос-ответ")
        verbose_name_plural = _("Вопросы и ответы")
        unique_together = (('type', 'order'),)
        indexes = [
            models.Index(fields=['type', 'order']),
        ]

    def __str__(self):
        return f"{self.get_type_display()}: {self.question[:50]}"
