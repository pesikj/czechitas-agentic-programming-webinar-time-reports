from django.core.management.base import BaseCommand
from django.utils import timezone

from imports.models import ImportBatch


class Command(BaseCommand):
    help = "Odstraní obsah importů s vypršelou platností; audit a otisk zůstanou."

    def handle(self, *args, **kwargs):
        count = (
            ImportBatch.objects.filter(expires_at__lte=timezone.now())
            .exclude(status="completed")
            .update(table={}, rows=[], errors=[], duplicates=[], status="expired")
        )
        self.stdout.write(f"Vyčištěno dávek: {count}")
