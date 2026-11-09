"""Submitted character stories and their review, independent from support tickets."""
import uuid

from django.conf import settings
from django.db import models


class CharacterStorySubmission(models.Model):
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    character = models.ForeignKey('home.TbPersonagem', on_delete=models.PROTECT,
                                  related_name='story_submissions')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name='character_stories')
    text = models.TextField(max_length=5000)
    text_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=16, default='pending', choices=[
        ('pending', 'Aguardando aprovação'), ('approved', 'Aprovada'),
        ('changes', 'Ajustes solicitados'), ('superseded', 'Substituída por novo envio')], db_index=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name='reviewed_character_stories')
    feedback = models.TextField(max_length=3000, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ['-submitted_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['character'], condition=models.Q(status='pending'),
                                              name='one_pending_character_story')]
