import pytest
from django.contrib.auth.tokens import default_token_generator

pytestmark = pytest.mark.django_db


def test_contractor_cannot_manage_accounts(client):
    from accounts.models import User

    user = User.objects.create_user(
        "person", email="person@example.com", password="a-long-test-password"
    )
    client.force_login(user)
    assert client.get("/manage/accounts/").status_code == 403


def test_setup_link_is_single_use(client):
    from urllib.parse import urlsplit

    from django.test import RequestFactory

    from accounts.models import User
    from accounts.services import issue_setup_link

    admin = User.objects.create_user("manager", email="manager@example.com", is_staff=True)
    user = User.objects.create_user("person", email="person@example.com")
    request = RequestFactory().get("/", HTTP_HOST="testserver")
    link = issue_setup_link(actor=admin, user=user, request=request)
    url = urlsplit(link).path
    response = client.get(url)
    assert response.status_code == 302  # hides token in session
    response = client.get(response.url)
    assert response.status_code == 200
    token = default_token_generator.make_token(user)
    response = client.post(
        response.request["PATH_INFO"],
        {"new_password1": "a-long-NewPassword-842!", "new_password2": "a-long-NewPassword-842!"},
    )
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("a-long-NewPassword-842!")
    assert not default_token_generator.check_token(user, token)


def test_deactivated_user_cannot_login(client):
    from accounts.models import User

    User.objects.create_user(
        "inactive", email="inactive@example.com", password="a-long-test-password", is_active=False
    )
    response = client.post("/login/", {"username": "inactive", "password": "a-long-test-password"})
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_setup_link_expires_after_24_hours(world, client):
    from datetime import datetime, timedelta
    from unittest.mock import patch
    from urllib.parse import urlsplit

    from django.test import RequestFactory

    from accounts.services import issue_setup_link

    now = datetime(2026, 10, 25, 12)
    with patch.object(default_token_generator, "_now", return_value=now):
        link = issue_setup_link(
            actor=world["manager"],
            user=world["person"],
            request=RequestFactory().get("/", HTTP_HOST="testserver"),
        )
    with patch.object(default_token_generator, "_now", return_value=now + timedelta(hours=25)):
        response = client.get(urlsplit(link).path)
    assert response.status_code == 200
    assert b"new_password1" not in response.content


def test_login_throttles_failed_attempts(world, client):
    for _ in range(6):
        client.post("/login/", {"username": "jana", "password": "wrong"})
    response = client.post("/login/", {"username": "jana", "password": "test-Jana-3894!"})
    assert response.status_code == 429
    assert "_auth_user_id" not in client.session


def test_bootstrap_admin_creates_owner_once_and_never_resets(world, monkeypatch):
    from io import StringIO

    from django.core.management import call_command
    from django.core.management.base import CommandError

    from accounts.models import User

    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "owner")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "first-Owner-Password-2391!")
    # Existing manager prevents this privileged, one-time initialization.
    with pytest.raises(CommandError):
        call_command("bootstrap_admin", stdout=StringIO())
    world["manager"].is_staff = False
    world["manager"].save()
    output = StringIO()
    call_command("bootstrap_admin", stdout=output)
    owner = User.objects.get(username="owner")
    assert owner.is_staff and owner.is_superuser
    assert owner.check_password("first-Owner-Password-2391!")
    assert "first-Owner-Password-2391!" not in output.getvalue()
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "different-Password-4927!")
    with pytest.raises(CommandError):
        call_command("bootstrap_admin", stdout=StringIO())
    owner.refresh_from_db()
    assert owner.check_password("first-Owner-Password-2391!")


def test_bootstrap_if_configured_skips_without_credentials(monkeypatch):
    from io import StringIO

    from django.core.management import call_command

    for key in ["BOOTSTRAP_ADMIN_USERNAME", "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD"]:
        monkeypatch.delenv(key, raising=False)
    # No account is created and no secret is required on ordinary later starts.
    call_command("bootstrap_admin", "--if-configured", stdout=StringIO())
