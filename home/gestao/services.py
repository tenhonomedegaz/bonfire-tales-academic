"""Audited manual grants. Existing inventory and permanent sources stay authoritative."""
import hashlib
import json
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from home.cosmetic_entitlements import has_permanent_cosmetic
from home.gestao_models import ManualCosmeticGrantReceipt
from home.models import TbCosmetico, TbUsuarioCosmetico
from .policy import can

SALT = 'bonfire.management.manual-grant.v1'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _require(actor):
    if not all(can(actor, capability) for capability in (
            'people.view', 'cosmetics.view', 'cosmetics.grant_manual')):
        raise PermissionDenied


def _state(user, cosmetic):
    inventory = TbUsuarioCosmetico.objects.filter(user=user, cosmetico=cosmetic).first()
    permanent = has_permanent_cosmetic(user, cosmetic)
    owned = cosmetic.origem == 'livre' or permanent or bool(inventory and not inventory.suspenso_em)
    blocked = ('A conta esta inativa.' if not user.is_active else
               'O cosmetico esta inativo.' if not cosmetic.ativo else
               'A concessao esta suspensa. A reativacao exige uma decisao separada.'
               if inventory and inventory.suspenso_em and not permanent else '')
    fingerprint = _digest({
        'user': [user.pk, user.is_active],
        'cosmetic': [cosmetic.pk, cosmetic.slug, cosmetic.nome, cosmetic.tipo, cosmetic.ativo,
                     cosmetic.origem, cosmetic.requer_plano, cosmetic.preco, cosmetic.escopo],
        'inventory': [inventory.pk, inventory.origem, inventory.suspenso_em] if inventory else None,
        'permanent': permanent,
    })
    return inventory, owned, blocked, fingerprint


def preview_manual_grant(*, actor, user_id, cosmetic_id, reason):
    _require(actor)
    reason = reason.strip() if isinstance(reason, str) else ''
    if not 5 <= len(reason) <= 500:
        raise ValidationError('Informe um motivo entre 5 e 500 caracteres.')
    try:
        user = get_user_model().objects.get(pk=user_id)
        cosmetic = TbCosmetico.objects.get(pk=cosmetic_id)
    except (get_user_model().DoesNotExist, TbCosmetico.DoesNotExist, ValueError, TypeError):
        raise ValidationError('Pessoa ou cosmetico nao encontrado.') from None
    inventory, owned, blocked, fingerprint = _state(user, cosmetic)
    payload = {'actor': actor.pk, 'user': user.pk, 'cosmetic': cosmetic.pk, 'reason': reason,
               'request_id': str(uuid4()), 'fingerprint': fingerprint}
    return {'target': user, 'cosmetic': cosmetic, 'reason': reason, 'already_owned': owned,
            'blocked_reason': blocked, 'can_apply': not blocked,
            'ticket': signing.dumps(payload, salt=SALT, compress=True) if not blocked else ''}


@transaction.atomic
def apply_manual_grant(*, actor, ticket, expected_user_id=None):
    _require(actor)
    try:
        data = signing.loads(ticket, salt=SALT, max_age=600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Previa invalida ou expirada. Confira o item novamente.') from None
    if data.get('actor') != actor.pk:
        raise PermissionDenied
    if expected_user_id is not None and data.get('user') != expected_user_id:
        raise ValidationError('A previa pertence a outra pessoa. Confira o destinatario novamente.')
    # Serialize the beneficiary; a new paid/achievement source is re-read before writing.
    users = {u.pk: u for u in get_user_model().objects.select_for_update().filter(
        pk__in={actor.pk, data['user']}).order_by('pk')}
    current_actor, user = users.get(actor.pk), users.get(data['user'])
    _require(current_actor)
    if user is None:
        raise ValidationError('A conta nao esta mais disponivel.')
    digest = _digest(data)
    receipt = ManualCosmeticGrantReceipt.objects.filter(request_id=data['request_id']).first()
    if receipt:
        if receipt.actor_id != actor.pk or receipt.payload_digest != digest:
            raise ValidationError('Identificador de operacao ja utilizado em outra concessao.')
        return receipt
    try:
        cosmetic = TbCosmetico.objects.select_for_update().get(pk=data['cosmetic'])
    except TbCosmetico.DoesNotExist:
        raise ValidationError('O cosmetico nao esta mais disponivel.') from None
    inventory, owned, blocked, fingerprint = _state(user, cosmetic)
    if blocked:
        raise ValidationError(blocked)
    if fingerprint != data['fingerprint']:
        raise ValidationError('O cadastro ou o direito mudou. Confira uma nova previa.')
    if not owned:
        inventory, created = TbUsuarioCosmetico.objects.get_or_create(
            user=user, cosmetico=cosmetic, defaults={'origem': 'staff'})
        if not created:
            if inventory.suspenso_em:
                raise ValidationError('O direito mudou durante a confirmacao. Confira uma nova previa.')
            owned = True  # A purchase/achievement writer won the unique inventory key.
    return ManualCosmeticGrantReceipt.objects.create(
        request_id=UUID(data['request_id']), actor=current_actor, user=user, cosmetico=cosmetic,
        inventory=inventory, motivo=data['reason'], payload_digest=digest,
        outcome='already_owned' if owned else 'granted')
