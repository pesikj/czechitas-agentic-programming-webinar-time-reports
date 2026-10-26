import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from accounts.models import User
from common.models import audit


class Command(BaseCommand):
    help = (
        "Jednorázově založí prvního správce z BOOTSTRAP_ADMIN_*; existující přístupy nikdy nemění."
    )

    def add_arguments(self, parser):
        parser.add_argument("--if-configured", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get("BOOTSTRAP_ADMIN_USERNAME", "")
        email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        if options.get("if_configured") and not any([username, email, password]):
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [385174927593])
        if User.objects.filter(is_staff=True).exists():
            owner = User.objects.filter(
                username=username, email=email, is_staff=True, is_superuser=True
            ).first()
            if options.get("if_configured") and owner and owner.check_password(password):
                self.stdout.write("Správce již byl inicializován; účet nebyl změněn.")
                return
            raise CommandError("Správce už existuje. Inicializace nebyla provedena.")
        if not username or not email or not password or "@" in username:
            raise CommandError(
                "Nastavte BOOTSTRAP_ADMIN_USERNAME, EMAIL a PASSWORD; jméno nesmí obsahovat @."
            )
        user = User(username=username, email=email, is_staff=True, is_superuser=True)
        try:
            validate_password(password, user=user)
            user.set_password(password)
            user.full_clean()
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.save()
        audit(user, "account.bootstrap", user)
        self.stdout.write("První správce byl vytvořen. Odstraňte BOOTSTRAP_ADMIN_* z prostředí.")
