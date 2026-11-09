"""Explicit role membership; no default permissions or technical flag promotion."""
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from home.gestao_models import ManagementRoleReceipt
from .services import _digest

ROLE_NAMES = ('Staff', 'Rulesmaster', 'Loremaster', 'Jornalista', 'Devmaster', 'Mediamaster')
SALT = 'bonfire.management.roles.v1'


def require_admin(actor):
    if not (actor and actor.is_authenticated and actor.is_active and actor.is_superuser):
        raise PermissionDenied


def permission_label(permission):
    action = permission.codename.partition('_')[0]
    model = permission.content_type.model_class()
    verbs = {'view': 'Consultar', 'add': 'Adicionar', 'change': 'Editar', 'delete': 'Excluir'}
    if action in verbs and model is not None and permission.codename == action + '_' + model._meta.model_name:
        return '%s %s' % (verbs[action], model._meta.verbose_name)
    return permission.name


def access_summary(user):
    permissions = {}
    groups = list(user.groups.prefetch_related('permissions__content_type').order_by('name'))
    for group in groups:
        for permission in group.permissions.all():
            row = permissions.setdefault(permission.pk, {
                'label': permission_label(permission), 'sources': []})
            row['sources'].append(group.name)
    for permission in user.user_permissions.select_related('content_type'):
        row = permissions.setdefault(permission.pk, {
            'label': permission_label(permission), 'sources': []})
        row['sources'].append('Permissão individual')
    return sorted(permissions.values(), key=lambda row: row['label'])


def role_catalog():
    groups = {g.name: g for g in Group.objects.filter(name__in=ROLE_NAMES)
              .prefetch_related('permissions__content_type')}
    return [{'name': name, 'configured': name in groups,
             'permissions': sorted(permission_label(p) for p in groups[name].permissions.all())
             if name in groups else []} for name in ROLE_NAMES]


def _state(user):
    groups = list(user.groups.order_by('pk').values_list('pk', 'name'))
    from django.db.models import Q
    catalog = list(Group.objects.filter(
        Q(name__in=ROLE_NAMES) | Q(pk__in=[pk for pk, _ in groups])).order_by('pk'))
    return _digest({
        'user': [user.pk, user.is_active, user.is_superuser, user.is_staff],
        'groups': groups,
        'direct': list(user.user_permissions.order_by('pk').values_list('pk', flat=True)),
        'roles': [[g.pk, g.name, list(g.permissions.order_by('pk').values_list('pk', flat=True))]
                  for g in catalog],
    })


def preview_roles(*, actor, user_id, roles, reason):
    require_admin(actor)
    if (not isinstance(roles, list)
            or not all(isinstance(r, str) and r in ROLE_NAMES for r in roles)
            or len(roles) != len(set(roles))):
        raise ValidationError('Selecione cargos válidos.')
    reason = reason.strip() if isinstance(reason, str) else ''
    if not 5 <= len(reason) <= 500:
        raise ValidationError('Informe um motivo entre 5 e 500 caracteres.')
    user = get_user_model().objects.get(pk=user_id)
    before = sorted(user.groups.filter(name__in=ROLE_NAMES).values_list('name', flat=True))
    selected = sorted(roles)
    payload = {'actor': actor.pk, 'user': user.pk, 'roles': selected,
               'reason': reason, 'version': _state(user), 'request_id': str(uuid4())}
    return {'before': before, 'after': selected,
            'added': sorted(set(selected) - set(before)),
            'removed': sorted(set(before) - set(selected)),
            'ticket': signing.dumps(payload, salt=SALT, compress=True)}


@transaction.atomic
def apply_roles(*, actor, user_id, ticket):
    require_admin(actor)
    try:
        data = signing.loads(ticket, salt=SALT, max_age=600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValidationError('Prévia inválida ou expirada. Confira os cargos novamente.') from None
    if data.get('actor') != actor.pk or data.get('user') != user_id:
        raise PermissionDenied
    users = {u.pk: u for u in get_user_model().objects.select_for_update().filter(
        pk__in={actor.pk, user_id}).order_by('pk')}
    require_admin(users.get(actor.pk))
    user = users.get(user_id)
    if user is None:
        raise ValidationError('Conta não encontrada.')
    receipt = ManagementRoleReceipt.objects.filter(request_id=data['request_id']).first()
    digest = _digest(data)
    if receipt:
        if receipt.actor_id != actor.pk or receipt.payload_digest != digest:
            raise ValidationError('Identificador já utilizado em outra alteração.')
        return receipt
    list(Group.objects.select_for_update().filter(name__in=ROLE_NAMES).order_by('pk'))
    if _state(user) != data['version']:
        raise ValidationError('A conta ou as permissões mudaram. Confira uma nova prévia.')
    before = sorted(user.groups.filter(name__in=ROLE_NAMES).values_list('name', flat=True))
    desired = data['roles']
    user.groups.remove(*Group.objects.filter(name__in=set(before) - set(desired)))
    for name in set(desired) - set(before):
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    return ManagementRoleReceipt.objects.create(
        request_id=UUID(data['request_id']), actor=users[actor.pk], user=user,
        before_roles=before, after_roles=desired, motivo=data['reason'], payload_digest=digest)
