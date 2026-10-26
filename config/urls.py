from django.contrib.auth import views as auth
from django.urls import path

from accounts import views as accounts
from calendar_app import views as calendar_views
from common.views import health
from contracts import views as contracts
from imports import views as imports
from reports import views as reports

urlpatterns = [
    path("health/", health, name="health"),
    path("calendar/", calendar_views.calendar_view, name="calendar"),
    path("calendar/new/", calendar_views.absence_form, name="absence_new"),
    path("calendar/<int:pk>/edit/", calendar_views.absence_form, name="absence_edit"),
    path("calendar/<int:pk>/cancel/", calendar_views.cancel, name="absence_cancel"),
    path("imports/", imports.upload, name="import_upload"),
    path("imports/example/", imports.example, name="import_example"),
    path("imports/<uuid:pk>/mapping/", imports.mapping, name="import_mapping"),
    path("imports/<uuid:pk>/", imports.preview, name="import_preview"),
    path("login/", auth.LoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path(
        "password/<uidb64>/<token>/",
        auth.PasswordResetConfirmView.as_view(success_url="/password-complete/"),
        name="password_setup",
    ),
    path(
        "password-complete/",
        auth.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("manage/accounts/", accounts.accounts, name="accounts"),
    path("manage/accounts/new/", accounts.account_form, name="account_new"),
    path("manage/accounts/<int:pk>/", accounts.account_form, name="account_edit"),
    path("manage/accounts/<int:pk>/setup-link/", accounts.setup_link, name="setup_link"),
    path("manage/contracts/", contracts.overview, name="contracts"),
    path("manage/contracts/<str:kind>/new/", contracts.contract_form, name="contract_new"),
    path("manage/contracts/<str:kind>/<int:pk>/", contracts.contract_form, name="contract_edit"),
    path("costs/", reports.costs, name="costs"),
    path("", reports.index, name="reports"),
    path("reports/new/", reports.create, name="report_create"),
    path("reports/<int:pk>/", reports.detail, name="report_detail"),
    path("reports/<int:pk>/entries/new/", reports.entry_form, name="entry_new"),
    path("reports/<int:pk>/entries/<int:entry_id>/", reports.entry_form, name="entry_edit"),
    path("entries/<int:entry_id>/delete/", reports.entry_delete, name="entry_delete"),
    path("reports/<int:pk>/submit/", reports.submit, name="report_submit"),
    path(
        "reports/<int:pk>/reopen/",
        reports.correction,
        {"operation": "reopen"},
        name="report_reopen",
    ),
    path(
        "reports/<int:pk>/reprice/",
        reports.correction,
        {"operation": "reprice"},
        name="report_reprice",
    ),
]
