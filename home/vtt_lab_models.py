"""Private Python laboratory state, independent of official character ledgers."""

import uuid

from django.conf import settings
from django.db import models


def initial_lab_state():
    return {'schema': 1, 'board': {'width': 24, 'height': 18, 'cell_meters': 1.5, 'cell_feet': 5,
            'metric': 'manhattan3d', 'movement': {'step_cost': 12, 'cost_scale': 12,
                'terrain_costs': {'normal': 1, 'difficult': 2}, 'allies': 'pass-through',
                'enemies': 'block', 'end_occupied': False}, 'blocked_cells': [], 'terrain_cells': {}},
            'tokens': [], 'turn': 0, 'events': []}


class VttLabSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vtt_lab_sessions')
    nome = models.CharField(max_length=120)
    state = models.JSONField(default=initial_lab_state)
    revision = models.PositiveBigIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'TB_VttLabSession'
        ordering = ['-atualizado_em', '-id']
        indexes = [models.Index(fields=['owner', '-atualizado_em'], name='vtt_lab_owner_updated_idx')]


class VttLabReceipt(models.Model):
    session = models.ForeignKey(VttLabSession, on_delete=models.CASCADE, related_name='receipts')
    command_id = models.UUIDField()
    payload_hash = models.CharField(max_length=64)
    revision = models.PositiveBigIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'TB_VttLabReceipt'
        constraints = [models.UniqueConstraint(fields=['session', 'command_id'], name='vtt_lab_command_unique')]
