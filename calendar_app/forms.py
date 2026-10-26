from django import forms

from accounts.models import User


class AbsenceForm(forms.Form):
    user = forms.ModelChoiceField(label="Externista", queryset=User.objects.none())
    start = forms.DateField(
        label="První den nepřítomnosti",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    end = forms.DateField(
        label="Poslední den včetně",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = (
            User.objects.filter(is_active=True).order_by("last_name", "username")
            if actor.is_staff
            else User.objects.filter(pk=actor.pk)
        )
        self.fields["user"].initial = actor.pk
        if not actor.is_staff:
            self.fields["user"].disabled = True
