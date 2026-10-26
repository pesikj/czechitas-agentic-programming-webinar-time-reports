from django.core.exceptions import PermissionDenied


def require_active(user):
    if not user or not user.is_authenticated or not user.is_active:
        raise PermissionDenied


def require_manager(user):
    require_active(user)
    if not user.is_staff:
        raise PermissionDenied


def require_owner_or_manager(actor, owner_id):
    require_active(actor)
    if not actor.is_staff and actor.pk != owner_id:
        raise PermissionDenied
