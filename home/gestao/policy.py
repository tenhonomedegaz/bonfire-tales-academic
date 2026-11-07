"""Task capabilities without is_staff or implicit promotion of existing groups."""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


CAPABILITIES = {
    'character_history.review': 'home.review_character_history',
    'people.view': 'home.view_management_people',
    'cosmetics.view': 'home.view_management_cosmetics',
    'cosmetics.grant_manual': 'home.grant_management_cosmetic',
}


def can(user, capability):
    permission = CAPABILITIES.get(capability)
    return bool(permission and user and user.is_authenticated and user.is_active
                and (user.is_superuser or user.has_perm(permission)))


def require_capability(capability):
    def decorator(view):
        @wraps(view)
        def guarded(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can(request.user, capability):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return guarded
    return decorator
