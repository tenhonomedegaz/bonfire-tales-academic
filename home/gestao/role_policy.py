"""Explicit administrator configuration of workspace capabilities only."""
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from home.gestao_models import ManagementRolePolicyReceipt
from .policy import CAPABILITIES
from .roles import ROLE_NAMES, permission_label, require_admin
from .services import _digest
from .workflows import QUEUES

SALT = 'bonfire.management.role-policy.v1'


def editable_permissions():
    codes = [value.split('.', 1)[1] for value in CAPABILITIES.values()]
    codes += ['review_portal_' + key for key in QUEUES]
    return list(Permission.objects.filter(content_type__app_label='home', codename__in=codes)
                .select_related('content_type').order_by('codename'))


def _state(role):
    group = Group.objects.filter(name=role).first()
    return {'group': group.pk if group else None,
            'permissions': list(group.permissions.order_by('pk').values_list('pk', flat=True)) if group else []}


def preview_policy(*, actor, role, permissions, reason):
    require_admin(actor)
    allowed = {str(p.pk) for p in editable_permissions()}
    if role not in ROLE_NAMES or not isinstance(permissions, list) or not set(permissions) <= allowed:
        raise ValidationError('Cargo ou permissão inválidos.')
    reason = reason.strip()
    if not 5 <= len(reason) <= 500:
        raise ValidationError('Informe o motivo entre 5 e 500 caracteres.')
    state = _state(role)
    desired = sorted(set(map(int, permissions)))
    current = sorted(set(state['permissions']) & set(map(int, allowed)))
    labels = {p.pk: permission_label(p) for p in editable_permissions()}
    data = {'actor': actor.pk, 'role': role, 'permissions': desired, 'reason': reason,
            'version': _digest(state), 'request_id': str(uuid4())}
    return {'added': [labels[pk] for pk in desired if pk not in current],
            'removed': [labels[pk] for pk in current if pk not in desired],
            'ticket': signing.dumps(data, salt=SALT, compress=True)}


@transaction.atomic
def apply_policy(*, actor, ticket):
    require_admin(actor)
    try:
        data = signing.loads(ticket, salt=SALT, max_age=600)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError('Prévia inválida ou expirada.') from None
    if data['actor'] != actor.pk:
        raise PermissionDenied
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    require_admin(actor)
    allowed = {p.pk for p in editable_permissions()}
    # A missing group has no row to lock; serialize policy creation on the shared capability rows.
    list(Permission.objects.select_for_update().filter(pk__in=allowed).order_by('pk'))
    digest = _digest(data)
    receipt = ManagementRolePolicyReceipt.objects.filter(request_id=data['request_id']).first()
    if receipt:
        if receipt.payload_digest != digest or receipt.actor_id != actor.pk:
            raise ValidationError('Operação já utilizada.')
        return receipt
    list(Group.objects.select_for_update().filter(name=data['role']))
    if _digest(_state(data['role'])) != data['version']:
        raise ValidationError('As permissões mudaram. Gere outra prévia.')
    if data['role'] not in ROLE_NAMES or not set(data['permissions']) <= allowed:
        raise ValidationError('A lista de permissões mudou. Gere outra prévia.')
    group, _ = Group.objects.get_or_create(name=data['role'])
    before = list(group.permissions.order_by('pk').values_list('pk', flat=True))
    group.permissions.remove(*[pk for pk in before if pk in allowed and pk not in data['permissions']])
    group.permissions.add(*data['permissions'])
    return ManagementRolePolicyReceipt.objects.create(request_id=UUID(data['request_id']),
        actor=actor, role_name=group.name, before_permissions=before,
        after_permissions=list(group.permissions.order_by('pk').values_list('pk', flat=True)),
        motivo=data['reason'], payload_digest=digest)
