from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from common.models import PageText, PageTextGlobalVersion


@receiver([post_save, post_delete], sender=PageText)
def update_global_version(sender, instance, **kwargs):
    PageTextGlobalVersion.bump()
