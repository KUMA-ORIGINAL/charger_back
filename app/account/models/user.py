from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from config import settings


class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier for authentication."""

    def _create_user(self, phone_number, password=None, **extra_fields):
        """Handles the common logic for user creation."""
        if not phone_number:
            raise ValueError(_("The phone_number field is required"))

        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, password, **extra_fields)

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self._create_user(phone_number, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Администратор'),
        ('agent', 'Агент'),
    )

    username = None
    phone_number = PhoneNumberField(_("Номер телефона"), blank=False, unique=True,
                                    help_text='Введите в формате 0 или 996')
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    middle_name = models.CharField(_("last name"), max_length=150, blank=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.phone_number} - {self.get_full_name()}"

    @property
    def full_name(self):
        """Общий доход (сумма дохода по ОСАГО и агентов)."""
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()


class ChargePoint(models.Model):
    """
    OCPP Charge Point
    """

    cp_id = models.CharField(
        primary_key=True,
        max_length=64,
        verbose_name=_("Charge Point ID"),
        help_text=_("ID станции (cp_id в URL WebSocket)"),
    )

    name = models.CharField(
        max_length=128,
        verbose_name=_("Name"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at"),
    )

    class Meta:
        verbose_name = _("Charge Point")
        verbose_name_plural = _("Charge Points")

    def __str__(self):
        return f"{self.cp_id}"
