"""Friendly validation before the database uniqueness guard."""
from django.contrib import admin
from django.contrib.auth import get_user_model

from .email_identity import available_email
from .models import UserAccountMergeReceipt


def with_unique_email(base):
    class UniqueEmailForm(base):
        def clean_email(self):
            return available_email(self.cleaned_data.get('email'), self.instance.pk)
    return UniqueEmailForm


if get_user_model() not in admin.site._registry:
    from django.contrib.auth import admin as auth_admin  # Registers Django's default UserAdmin.
user_admin = admin.site._registry[get_user_model()]
user_admin.form = with_unique_email(user_admin.form)
user_admin.add_form = with_unique_email(user_admin.add_form)


@admin.register(UserAccountMergeReceipt)
class AccountMergeReceiptAdmin(admin.ModelAdmin):
    list_display = ('keeper', 'removed_user_id', 'removed_username', 'email_verification_preserved', 'created_at')
    readonly_fields = list_display

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
