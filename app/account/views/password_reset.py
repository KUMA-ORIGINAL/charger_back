import random
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.utils import timezone

from ..forms import PhoneForm, CodeForm, NewPasswordForm
from ..models import PhoneVerification
from ..services import send_sms

User = get_user_model()


def request_code_view(request):
    if request.method == "POST":
        form = PhoneForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]

            try:
                user = User.objects.get(phone_number=phone)
            except User.DoesNotExist:
                messages.error(request, "Пользователь с таким номером не найден.")
                return render(request, "admin/password_reset_by_phone.html", {"form": form})

            code = f"{random.randint(100000, 999999)}"

            otp = PhoneVerification.objects.create(phone=phone, code=code)

            text = f"Код для сброса пароля: {code}"
            if send_sms(phone=phone, text=text, transaction_id=otp.id):
                request.session['reset_phone'] = phone
                messages.success(request, "Код подтверждения отправлен.")
                return redirect("verify_code")
            else:
                otp.delete()
                messages.error(request, "Не удалось отправить SMS.")
    else:
        form = PhoneForm()

    return render(request, "admin/password_reset_by_phone.html", {"form": form})


def verify_code_view(request):
    phone = request.session.get('reset_phone')

    if not phone:
        messages.error(request, "Сначала введите номер телефона.")
        return redirect('admin_password_reset')

    if request.method == "POST":
        form = CodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]

            # Определяем время "протухания" кода
            code_lifetime = timedelta(minutes=10)
            time_threshold = timezone.now() - code_lifetime

            # Пытаемся найти подходящий код
            verification = PhoneVerification.objects.filter(
                phone=phone,
                code=code,
                is_verified=False,
                created_at__gte=time_threshold
            ).order_by('-created_at').first()

            if verification:
                verification.is_verified = True
                verification.save()

                # Помечаем, что пользователь верифицирован
                request.session['verified_phone'] = phone
                request.session.pop('phone', None)  # удаляем старое значение

                messages.success(request, "Код подтверждён. Установите новый пароль.")
                return redirect('set_new_password')
            else:
                messages.error(request, "Неверный или просроченный код.")
    else:
        form = CodeForm()

    return render(request, "admin/verify_code.html", {"form": form})


def set_new_password_view(request):
    phone = request.session.get("verified_phone")  # используем проверенный номер

    if not phone:
        messages.error(request, "Сначала подтвердите код.")
        return redirect("verify_code")

    if request.method == "POST":
        form = NewPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data["password1"]

            try:
                user = User.objects.get(phone_number=phone)  # или username=phone, если нужно

                try:
                    validate_password(password, user)
                except ValidationError as e:
                    form.add_error("password1", e)
                    return render(request, "admin/set_new_password.html", {"form": form})

                user.set_password(password)
                user.save()

                request.session.pop("verified_phone", None)

                messages.success(request, "Пароль успешно изменён. Теперь вы можете войти.")
                return redirect('/admin/')

            except User.DoesNotExist:
                form.add_error(None, "Пользователь не найден.")
    else:
        form = NewPasswordForm()

    return render(request, "admin/set_new_password.html", {"form": form})