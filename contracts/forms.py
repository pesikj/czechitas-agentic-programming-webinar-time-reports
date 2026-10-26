from django import forms

from .models import Assignment, ContractTerms, Project

DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["code", "name", "is_active"]


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["user", "project", "start", "end", "is_active"]
        labels = {"user": "Externista", "project": "Projekt"}
        widgets = {"start": DATE_WIDGET, "end": DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["user"].disabled = True
            self.fields["project"].disabled = True


class TermsForm(forms.ModelForm):
    limit_hours = forms.DecimalField(
        label="Měsíční limit hodin", min_value=0.02, max_value=10000, decimal_places=2
    )

    class Meta:
        model = ContractTerms
        fields = ["assignment", "start_month", "end_month", "hourly_rate"]
        widgets = {"start_month": DATE_WIDGET, "end_month": DATE_WIDGET}
        labels = {"assignment": "Přiřazení"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["assignment"].disabled = True
            self.fields["limit_hours"].initial = self.instance.monthly_limit_minutes / 60

    def clean_limit_hours(self):
        value = self.cleaned_data["limit_hours"] * 60
        if value != value.to_integral_value():
            raise forms.ValidationError("Limit musí odpovídat celým minutám.")
        return self.cleaned_data["limit_hours"]

    def _post_clean(self):
        if "limit_hours" in self.cleaned_data:
            self.instance.monthly_limit_minutes = int(self.cleaned_data["limit_hours"] * 60)
        super()._post_clean()
