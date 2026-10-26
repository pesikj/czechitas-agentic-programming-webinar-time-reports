from django import forms
from django.core.exceptions import ValidationError

from .models import User


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active", "is_staff"]
        labels = {"is_staff": "Správce aplikace"}

    def clean_email(self):
        value = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Tento e-mail už má jiný účet.")
        return value

    def clean_username(self):
        value = self.cleaned_data["username"]
        if "@" in value:
            raise ValidationError(
                "Uživatelské jméno nesmí obsahovat @; pro přihlášení lze použít také e-mail."
            )
        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Toto uživatelské jméno již existuje.")
        return value
