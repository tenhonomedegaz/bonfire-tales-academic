"""Management receipts, not another source of balances or purchased rights."""
import uuid

from django.conf import settings
from django.db import models


class ManualCosmeticGrantReceipt(models.Model):
    request_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name='management_cosmetic_actions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                             related_name='management_cosmetic_receipts')
    cosmetico = models.ForeignKey('home.TbCosmetico', on_delete=models.PROTECT,
                                  related_name='management_grant_receipts')
    inventory = models.ForeignKey('home.TbUsuarioCosmetico', on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='management_receipts')
    motivo = models.CharField(max_length=500)
    payload_digest = models.CharField(max_length=64, editable=False)
    outcome = models.CharField(max_length=20, choices=[
        ('granted', 'Concedido'), ('already_owned', 'Ja possuido')])
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-request_id']
        default_permissions = ()
        permissions = [
            ('view_management_people', 'Consultar pessoas na Central de Gestao'),
            ('view_management_cosmetics', 'Consultar inventarios na Central de Gestao'),
            ('grant_management_cosmetic', 'Conceder cosmetico manual pela Central de Gestao'),
        ]
