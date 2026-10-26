from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import User


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        candidates = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username))
        if candidates.count() != 1:
            User().set_password(password)
            return None
        user = candidates.first()
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
