"""Site-native requests and immutable activity, not a parallel identity database."""
import uuid

from django.conf import settings
from django.db import models

from .gestao.workflows import QUEUES, STATUSES


class PortalRequest(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    payload_digest = models.CharField(max_length=64, editable=False)
    queue = models.CharField(max_length=24, choices=[(key, value[0]) for key, value in QUEUES.items()])
    title = models.CharField(max_length=200)
    description = models.TextField(max_length=8000)
    reference_url = models.URLField(max_length=2000, blank=True)
    character = models.ForeignKey('home.TbPersonagem', null=True, blank=True,
                                  on_delete=models.PROTECT, related_name='portal_requests')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name='portal_requests')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.PROTECT, related_name='portal_assignments')
    status = models.CharField(max_length=16, choices=STATUSES, default='new', db_index=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def reference(self):
        return '%s-%05d' % (QUEUES[self.queue][2], self.pk)

    class Meta:
        default_permissions = ()
        ordering = ['-updated_at', '-pk']
        permissions = [('review_portal_' + key, 'Atender ' + value[0]) for key, value in QUEUES.items()]


class PortalActivity(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    task = models.ForeignKey(PortalRequest, on_delete=models.PROTECT, related_name='activities')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=20)
    note = models.TextField(max_length=8000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    payload_digest = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['created_at', 'pk']
