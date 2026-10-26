from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.models import audit
from common.permissions import require_manager


def issue_setup_link(*, actor, user, request):
    require_manager(actor)
    token = default_token_generator.make_token(user)
    path = reverse(
        "password_setup",
        kwargs={"uidb64": urlsafe_base64_encode(force_bytes(user.pk)), "token": token},
    )
    audit(actor, "account.setup_link", user)
    return request.build_absolute_uri(path)
