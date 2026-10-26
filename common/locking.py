from accounts.models import User


def lock_person(user_id):
    return User.objects.select_for_update().get(pk=user_id)
