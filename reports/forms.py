from django import forms

from contracts.models import Assignment

from .services import hours_to_minutes


class MonthForm(forms.Form):
    month = forms.DateField(
        label="Měsíc",
        input_formats=["%Y-%m"],
        widget=forms.DateInput(attrs={"type": "month"}, format="%Y-%m"),
    )


class EntryForm(forms.Form):
    date = forms.DateField(
        label="Datum", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    assignment = forms.ModelChoiceField(label="Projekt", queryset=Assignment.objects.none())
    hours = forms.CharField(
        label="Počet hodin", help_text="Např. 1,5 pro hodinu a půl.", max_length=20
    )
    description = forms.CharField(
        label="Popis práce",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, user_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignment"].queryset = Assignment.objects.filter(
            user_id=user_id, is_active=True, project__is_active=True
        ).select_related("project", "user")

    def clean_hours(self):
        return hours_to_minutes(self.cleaned_data["hours"])


class ReasonForm(forms.Form):
    reason = forms.CharField(
        label="Důvod", max_length=1000, widget=forms.Textarea(attrs={"rows": 3})
    )
