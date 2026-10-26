from django import forms


class UploadForm(forms.Form):
    file = forms.FileField(
        label="Historický výkaz (.xlsx nebo CSV)",
        help_text="Nejvýše 5 MiB a 10 000 záznamů. CSV musí být v UTF-8.",
    )
    sheet = forms.CharField(
        label="Název listu Excelu",
        max_length=100,
        required=False,
        help_text="Vyplňte, pokud sešit obsahuje více listů.",
    )


class MappingForm(forms.Form):
    def __init__(self, *args, headers, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "date": "Datum práce",
            "user": "Externista (uživatelské jméno nebo e-mail)",
            "project": "Kód projektu",
            "hours": "Počet hodin",
            "description": "Popis práce (volitelné)",
        }
        defaults = {
            "date": ["datum", "date"],
            "user": ["externista", "user", "email", "e-mail"],
            "project": ["projekt", "project"],
            "hours": ["hodiny", "hours"],
            "description": ["popis", "description"],
        }
        for key, label in labels.items():
            choices = [("", "— Vyberte sloupec —")] + [(h, h) for h in headers]
            initial = next((h for h in headers if h.lower() in defaults[key]), "")
            self.fields[key] = forms.ChoiceField(
                label=label, choices=choices, required=key != "description", initial=initial
            )


class ConfirmForm(forms.Form):
    accept_duplicates = forms.BooleanField(
        label="Shodné řádky jsou správně a mají být započítány samostatně.", required=False
    )
