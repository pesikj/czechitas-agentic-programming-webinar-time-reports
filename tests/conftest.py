import os

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-for-local-tests-92847162938471629384")
os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("DATABASE_URL", "postgresql://jiripesik@127.0.0.1:55432/time_reports")

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture
def world(db):
    from accounts.models import User
    from contracts.models import Assignment, ContractTerms, Project
    from reports.models import MonthlyReport

    manager = User.objects.create_user(
        "manager", email="manager@example.com", password="test-Manager-3894!", is_staff=True
    )
    person = User.objects.create_user(
        "jana",
        email="jana@example.com",
        password="test-Jana-3894!",
        first_name="Jana",
        last_name="Nováková",
    )
    other = User.objects.create_user(
        "petr",
        email="petr@example.com",
        password="test-Petr-3894!",
        first_name="Petr",
        last_name="Svoboda",
    )
    assignments = []
    for code, rate in [("WEB", "800"), ("DATA", "1000")]:
        project = Project.objects.create(
            code=code, name={"WEB": "Webová aplikace", "DATA": "Datová analýza"}[code]
        )
        assignment = Assignment.objects.create(user=person, project=project, start=date(2026, 1, 1))
        ContractTerms.objects.create(
            assignment=assignment,
            start_month=date(2026, 1, 1),
            hourly_rate=Decimal(rate),
            monthly_limit_minutes=1200,
        )
        assignments.append(assignment)
    report = MonthlyReport.objects.create(user=person, month=date(2026, 10, 1))
    return {
        "manager": manager,
        "person": person,
        "other": other,
        "assignments": assignments,
        "report": report,
    }


@pytest.fixture(scope="session")
def django_db_modify_db_settings(django_db_modify_db_settings_parallel_suffix):
    from django.conf import settings

    # Worker/live-server requests must close test connections before DB teardown.
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup):
    import psycopg
    from django.conf import settings
    from django.db import connections

    test_name = settings.DATABASES["default"]["NAME"]
    yield
    connections.close_all()
    # Only dispose connections to pytest's isolated DB, after live server teardown.
    # Never terminate connections to the source database or any production DB.
    if str(test_name).startswith("test_"):
        with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                [test_name],
            )
