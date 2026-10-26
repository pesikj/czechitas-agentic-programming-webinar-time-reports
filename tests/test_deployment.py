import os
import subprocess
import sys

import pytest
from django.db import OperationalError


def test_production_requires_secrets_and_database():
    for missing in ["SECRET_KEY", "DATABASE_URL"]:
        env = {**os.environ, "DEBUG": "0"}
        env.pop(missing, None)
        result = subprocess.run(
            [sys.executable, "manage.py", "check"], env=env, capture_output=True, text=True
        )
        assert result.returncode != 0
        assert missing in result.stderr


@pytest.mark.django_db
def test_health_checks_database(client, monkeypatch):
    assert client.get("/health/").status_code == 200
    import common.views

    def unavailable(*args, **kwargs):
        raise OperationalError("secret database failure details")

    monkeypatch.setattr(common.views.connection, "ensure_connection", unavailable)
    response = client.get("/health/")
    assert response.status_code == 503
    assert b"secret database" not in response.content


def test_production_cookie_and_csrf_settings():
    env = {
        **os.environ,
        "DEBUG": "0",
        "SECRET_KEY": "isolated-production-config-check-key-with-sufficient-length-392842",
        "ALLOWED_HOSTS": "example.com",
        "CSRF_TRUSTED_ORIGINS": "https://example.com",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "no issues" in result.stdout


@pytest.mark.django_db
def test_security_headers_and_csrf(world):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(world["person"])
    assert client.post(f"/reports/{world['report'].pk}/submit/").status_code == 403
    response = client.get("/")
    assert response["Content-Security-Policy"].startswith("default-src 'self'")
    assert response["X-Frame-Options"] == "DENY"
