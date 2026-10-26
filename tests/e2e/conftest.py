import os
from pathlib import Path

import pytest


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    with sync_playwright() as runtime:
        options = {"executable_path": str(chrome)} if chrome.exists() else {}
        browser = runtime.chromium.launch(**options)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        yield context.new_page()
        context.close()
        browser.close()


# Playwright's sync API maintains an asyncio loop in the test thread. Our WSGI
# application remains synchronous; allow synchronous test-only fixture/ORM work
# while that loop is alive, and restore Django's guard after the E2E teardown.


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    item._previous_async_unsafe = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    try:
        yield
    finally:
        old = item._previous_async_unsafe
        if old is None:
            os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
        else:
            os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = old


@pytest.fixture(autouse=True)
def source_static_files(settings):
    # Django's live-server StaticFilesHandler resolves source names rather than
    # collectstatic's hashed production names. WhiteNoise is verified in Docker.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
