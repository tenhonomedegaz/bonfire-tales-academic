"""Audited identity/narrative corrections; never a general character-model editor."""
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from home.models import TbPersonagem
from home.portal_models import PortalActivity, PortalRequest
from .policy import can
from .services import _digest
from .workflows import can_review

PROFILE_FIELDS = {
    'nome': 'Nome do personagem', 'tagline': 'Frase de apresentação', 'jogador': 'Nome de exibição do jogador',
    'idade': 'Idade', 'altura': 'Altura', 'peso': 'Peso', 'genero': 'Gênero',
    'olhos': 'Olhos', 'cabelo': 'Cabelo', 'pele': 'Pele',
    'aparencia': 'Descrição da aparência', 'anotacoes': 'Anotações de lore',
    'notas_jogador': 'Notas de mesa',
}
TEXT_LIMITS = {'aparencia': 5000, 'anotacoes': 5000, 'notas_jogador': 8000}
FORM_SALT = 'bonfire.management.character-profile.form.v1'
PREVIEW_SALT = 'bonfire.management.character-profile.preview.v1'


def can_correct_profile(actor, task):
    return bool(can(actor, 'characters.profile') and can_review(actor, 'ficha')
                and task.queue == 'ficha' and task.character_id
                and task.status == 'reviewing' and task.assignee_id == actor.pk)


def _require(actor, task):
    if not can_correct_profile(actor, task):
        raise PermissionDenied


def profile_values(person):
    return {key: getattr(person, key) or '' for key in PROFILE_FIELDS}


def _state(task):
    person = task.character
    return _digest({'task': [task.pk, task.version, task.status, task.queue, task.assignee_id],
        'person': [person.pk, person.dono_id, person.arquivado, person.dono.is_active],
        'values': profile_values(person)})


def edit_token(actor, task):
    _require(actor, task)
    return signing.dumps({'actor': actor.pk, 'task': task.pk, 'version': _state(task)}, salt=FORM_SALT)


def validate_changes(changes):
    if not isinstance(changes, dict) or not changes or set(changes) - PROFILE_FIELDS.keys():
        raise ValidationError('A correção contém campos não permitidos ou está vazia.')
    clean = {}
    for key, value in changes.items():
        field = TbPersonagem._meta.get_field(key)
        limit = field.max_length or TEXT_LIMITS[key]
        if not isinstance(value, str) or '\x00' in value or len(value.strip()) > limit:
            raise ValidationError('%s: confira o texto e o limite de %d caracteres.' % (PROFILE_FIELDS[key], limit))
        value = value.strip()
        if key == 'nome' and not value:
            raise ValidationError('O nome do personagem não pode ficar vazio.')
        clean[key] = value or (None if field.null else '')
    return clean


def preview_profile(*, actor, task_id, base_token, changes, reason, evidence, finish=False):
    task = PortalRequest.objects.select_related('character__dono').get(pk=task_id)
    _require(actor, task)
    person = task.character
    if person.arquivado or not person.dono.is_active:
        raise ValidationError('A ficha está arquivada ou a conta do dono está inativa.')
    try:
        base = signing.loads(base_token, salt=FORM_SALT, max_age=3600)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError('A edição expirou. Reabra o formulário para conferir os dados atuais.') from None
    if base.get('actor') != actor.pk or base.get('task') != task.pk:
        raise PermissionDenied
    if base['version'] != _state(task):
        raise ValidationError('A ficha ou o atendimento mudou desde a abertura. Recarregue antes de conferir.')
    clean = validate_changes(changes)
    clean = {key: value for key, value in clean.items() if (value or '') != (getattr(person, key) or '')}
    if not clean:
        raise ValidationError('Nenhuma alteração foi selecionada.')
    reason = reason.strip() if isinstance(reason, str) else ''
    evidence = evidence.strip() if isinstance(evidence, str) else ''
    if not 5 <= len(reason) <= 500 or not 5 <= len(evidence) <= 2000:
        raise ValidationError('Informe motivo e evidência da correção.')
    data = {'actor': actor.pk, 'task': task.pk, 'character': person.pk,
        'version': _state(task), 'changes': clean, 'reason': reason, 'evidence': evidence,
        'finish': bool(finish), 'request_id': str(uuid4())}
    return {'person': person, 'rows': [{'label': PROFILE_FIELDS[key],
            'before': getattr(person, key) or '', 'after': value or ''} for key, value in clean.items()],
        'reason': reason, 'evidence': evidence, 'finish': bool(finish),
        'ticket': signing.dumps(data, salt=PREVIEW_SALT, compress=True)}


@transaction.atomic
def apply_profile(*, actor, task_id, ticket):
    if not can(actor, 'characters.profile') or not can_review(actor, 'ficha'):
        raise PermissionDenied
    try:
        data = signing.loads(ticket, salt=PREVIEW_SALT, max_age=600)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError('Prévia inválida ou expirada. Confira novamente.') from None
    if data.get('actor') != actor.pk or data.get('task') != task_id:
        raise PermissionDenied
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not can(actor, 'characters.profile') or not can_review(actor, 'ficha'):
        raise PermissionDenied
    task = PortalRequest.objects.select_for_update().get(pk=task_id)
    digest = _digest(data)
    receipt = PortalActivity.objects.filter(request_id=data['request_id']).first()
    if receipt:
        if receipt.actor_id != actor.pk or receipt.task_id != task.pk or receipt.payload_digest != digest:
            raise ValidationError('Identificador já utilizado em outra operação.')
        return receipt
    _require(actor, task)
    person = TbPersonagem.objects.select_for_update().select_related('dono').get(pk=task.character_id)
    task.character = person
    if person.pk != data['character'] or _state(task) != data['version']:
        raise ValidationError('A ficha ou o atendimento mudou. Confira uma nova prévia.')
    if person.arquivado or not person.dono.is_active:
        raise ValidationError('A ficha não está disponível para correção.')
    changes = validate_changes(data['changes'])
    before = {key: getattr(person, key) for key in changes}
    for key, value in changes.items():
        setattr(person, key, value)
    person.save(update_fields=[*changes, 'atualizado_em'])
    previous_version = task.version
    task.version += 1
    if data['finish']:
        task.status = 'done'
    task.save(update_fields=['status', 'version', 'updated_at'])
    return PortalActivity.objects.create(request_id=UUID(data['request_id']), task=task, actor=actor,
        action='profile', note=data['reason'] + '\nEvidência: ' + data['evidence'],
        before={'version': previous_version, 'character': person.pk, 'fields': before},
        after={'version': task.version, 'status': task.status, 'character': person.pk, 'fields': changes},
        payload_digest=digest)
