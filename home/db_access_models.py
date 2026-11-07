"""Persistent state for the restricted database access API.

This module intentionally lives outside ``models.py`` so the feature remains
isolated.  Importing it registers the models under the existing ``home`` app.
"""
import hashlib
import hmac
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class ManagedApiKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=16, unique=True, db_index=True)
    secret_hash = models.CharField(max_length=64, editable=False)
    scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_api_keys_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    rotated_from = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rotations',
    )
    rate_window_started = models.DateTimeField(null=True, blank=True)
    rate_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'home_managed_api_key'
        ordering = ('-created_at',)
        verbose_name = 'Chave de API gerenciada'
        verbose_name_plural = 'Chaves de API gerenciadas'

    @staticmethod
    def digest(secret):
        return hashlib.sha256(secret.encode('utf-8')).hexdigest()

    @classmethod
    def new_secret(cls):
        return 'bfd_' + secrets.token_urlsafe(32)

    def matches(self, secret):
        return hmac.compare_digest(self.secret_hash, self.digest(secret))

    def is_usable(self, now=None):
        now = now or timezone.now()
        return not self.revoked_at and (not self.expires_at or self.expires_at > now)

    def has_scope(self, scope):
        return scope in (self.scopes or [])

    def __str__(self):
        return '%s (%s)' % (self.name, self.prefix)


class DbAccessIdempotency(models.Model):
    api_key = models.ForeignKey(ManagedApiKey, on_delete=models.CASCADE)
    key_hash = models.CharField(max_length=64)
    request_hash = models.CharField(max_length=64)
    status_code = models.PositiveSmallIntegerField()
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'home_db_access_idempotency'
        constraints = [
            models.UniqueConstraint(
                fields=('api_key', 'key_hash'),
                name='home_db_access_idempotency_key_unique',
            ),
        ]


class DbAccessAudit(models.Model):
    api_key = models.ForeignKey(
        ManagedApiKey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action = models.CharField(max_length=24)
    model_label = models.CharField(max_length=64, blank=True)
    object_pk = models.CharField(max_length=100, blank=True)
    status_code = models.PositiveSmallIntegerField()
    field_names = models.JSONField(default=list, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'home_db_access_audit'
        ordering = ('-occurred_at',)
        verbose_name = 'Auditoria de acesso ao banco'
        verbose_name_plural = 'Auditorias de acesso ao banco'
