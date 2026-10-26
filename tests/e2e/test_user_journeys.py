from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone
from playwright.sync_api import expect

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def login(page, base, name, password):
    page.goto(base + "/login/")
    expect(page.locator("body")).to_have_css("background-color", "rgb(245, 247, 246)")
    page.get_by_label("Uživatelské jméno").fill(name)
    page.locator("#id_password").fill(password)
    page.get_by_role("button", name="Přihlásit se").click()
    expect(page.get_by_role("heading", name="Výkazy práce")).to_be_visible()


def test_manager_setup_then_contractor_submission_and_notice(page, live_server, world):
    login(page, live_server.url, "manager", "test-Manager-3894!")
    page.get_by_role("link", name="Lidé a přístupy").click()
    page.get_by_role("link", name="Přidat člověka").click()
    page.locator("#id_username").fill("lucie")
    page.locator("#id_email").fill("lucie@example.com")
    page.locator("#id_first_name").fill("Lucie")
    page.get_by_role("button", name="Uložit", exact=True).click()
    expect(page.get_by_role("cell", name="lucie@example.com", exact=True)).to_be_visible()
    page.get_by_role("link", name="Projekty a smlouvy").click()
    page.get_by_role("link", name="Nový projekt").click()
    page.locator("#id_code").fill("DESIGN")
    page.locator("#id_name").fill("Nová vizuální identita")
    page.get_by_role("button", name="Uložit", exact=True).click()
    page.get_by_role("link", name="Přidat přiřazení").click()
    page.locator("#id_user").select_option(str(world["person"].pk))
    from contracts.models import Project

    project = Project.objects.get(code="DESIGN")
    page.locator("#id_project").select_option(str(project.pk))
    page.locator("#id_start").fill("2026-01-01")
    page.get_by_role("button", name="Uložit", exact=True).click()
    page.get_by_role("link", name="Přidat podmínky").click()
    from contracts.models import Assignment

    assignment = Assignment.objects.get(user=world["person"], project=project)
    page.locator("#id_assignment").select_option(str(assignment.pk))
    page.locator("#id_start_month").fill("2026-01-01")
    page.locator("#id_hourly_rate").fill("900")
    page.locator("#id_limit_hours").fill("80")
    page.get_by_role("button", name="Uložit", exact=True).click()
    expect(page.get_by_role("heading", name="Projekty a smlouvy")).to_be_visible()
    page.get_by_role("button", name="Odhlásit se").click()
    login(page, live_server.url, "jana@example.com", "test-Jana-3894!")
    page.goto(live_server.url + f"/reports/{world['report'].pk}/")
    page.get_by_role("link", name="Zapsat práci").click()
    page.locator("#id_date").fill("2026-10-01")
    page.locator("#id_assignment").select_option(str(world["assignments"][0].pk))
    page.locator("#id_hours").fill("8")
    page.locator("#id_description").fill("Implementace klientského portálu")
    page.get_by_role("button", name="Uložit", exact=True).click()
    page.get_by_role("button", name="Odeslat výkaz").click()
    expect(page.get_by_text("Výkaz byl odeslán a zamčen.")).to_be_visible()
    page.get_by_role("link", name="Kalendář týmu").click()
    page.get_by_role("link", name="Naplánovat nepřítomnost").click()
    today = timezone.localdate()
    early = today + timedelta(days=13)
    valid = today + timedelta(days=14)
    page.locator("#id_start").fill(early.isoformat())
    page.locator("#id_end").fill(valid.isoformat())
    page.get_by_role("button", name="Uložit nepřítomnost").click()
    expect(page.locator(".errorlist")).to_contain_text("14 dní")
    page.locator("#id_start").fill(valid.isoformat())
    page.get_by_role("button", name="Uložit nepřítomnost").click()
    expect(page.get_by_text("Nepřítomnost byla uložena.")).to_be_visible()
    page.goto(live_server.url + "/calendar/?month=" + valid.strftime("%Y-%m"))
    Path("artifacts/qa").mkdir(parents=True, exist_ok=True)
    page.screenshot(path="artifacts/qa/calendar-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("button", name="Odhlásit se")).to_be_visible()
    page.screenshot(path="artifacts/qa/calendar-mobile.png", full_page=False)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_import_preview_costs_and_mobile(page, live_server, world, tmp_path):
    login(page, live_server.url, "manager", "test-Manager-3894!")
    page.get_by_role("link", name="Import historie").click()
    file = tmp_path / "history.csv"
    file.write_text(
        "Datum;Externista;Projekt;Hodiny;Popis\n2026-09-01;jana;WEB;1,5;Analýza požadavků\n2026-09-02;jana;DATA;2;Příprava dat\n",
        encoding="utf-8",
    )
    page.locator("#id_file").set_input_files(file)
    page.get_by_role("button", name="Pokračovat").click()
    expect(page.get_by_role("heading", name="Přiřazení sloupců")).to_be_visible()
    page.get_by_role("button", name="Zkontrolovat data").click()
    expect(page.get_by_text("Kontrola proběhla v pořádku.", exact=False)).to_be_visible()
    page.get_by_role("button", name="Potvrdit import").click()
    expect(page.get_by_role("heading", name="Historie je na svém místě.")).to_be_visible()
    page.goto(live_server.url + "/costs/?month=2026-09")
    expect(page.get_by_text("3200,00", exact=False)).to_be_visible()
    Path("artifacts/qa").mkdir(parents=True, exist_ok=True)
    page.screenshot(path="artifacts/qa/costs-desktop.png", full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path="artifacts/qa/costs-mobile.png", full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_over_limit_form_keeps_draft(page, live_server, world):
    login(page, live_server.url, "jana", "test-Jana-3894!")
    page.goto(live_server.url + f"/reports/{world['report'].pk}/")
    page.get_by_role("link", name="Zapsat práci").click()
    page.locator("#id_date").fill("2026-10-01")
    page.locator("#id_assignment").select_option(str(world["assignments"][0].pk))
    page.locator("#id_hours").fill("8,1")
    page.get_by_role("button", name="Uložit", exact=True).click()
    expect(page.get_by_text("překročení 6 minut.", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Odeslat výkaz")).to_be_disabled()
    page.screenshot(path="artifacts/qa/report-limit.png", full_page=True)
