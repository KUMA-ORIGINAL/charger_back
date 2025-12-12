from django import forms


PHONE_REGEX = r'^\+996\d{9}$'  # +996 и 9 цифр (например, +996700123456)


class PhoneForm(forms.Form):
    phone = forms.RegexField(
        regex=PHONE_REGEX,
        label="Номер телефона",
        error_messages={
            "invalid": "Введите корректный номер телефона в формате +996XXXXXXXXX",
        },
        widget=forms.TextInput(attrs={
            "placeholder": "+996",
            "autocomplete": "tel",
        })
    )


class CodeForm(forms.Form):
    code = forms.CharField(label="Код подтверждения", max_length=6)


class NewPasswordForm(forms.Form):
    password1 = forms.CharField(label="Новый пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают.")
        return cleaned_data
