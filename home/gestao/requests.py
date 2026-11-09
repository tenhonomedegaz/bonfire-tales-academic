"""Audited workflow commands; completing a request does not edit its character."""
from uuid import UUID, uuid5

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Q

from home.models import TbPersonagem
from home.portal_models import PortalActivity, PortalRequest
from .services import _digest
from .policy import can
from .workflows import QUEUES, allowed_actions, can_review, review_queues


def visible_requests(user):
    if not user.is_authenticated or not user.is_active:
        return PortalRequest.objects.none()
    return PortalRequest.objects.filter(Q(requester=user) | Q(queue__in=review_queues(user)))


def _text(value, maximum, label, minimum=0):
    if not isinstance(value, str) or '\x00' in value or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError('Confira o campo %s.' % label)
    return value.strip()


def _uuid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Identificador de operação inválido.') from None


def _actor(user):
    user = get_user_model().objects.get(pk=user.pk)
    if not user.is_active:
        raise PermissionDenied
    return user


@transaction.atomic
def create_request(*, actor, request_id, queue, title, description, reference_url='', character_id=None,
                   requester_id=None):
    actor = _actor(actor)
    if queue not in QUEUES:
        raise ValidationError('Fila inválida.')
    title = _text(title, 200, 'título', 3)
    description = _text(description, 8000, 'descrição', 5)
    reference_url = _text(reference_url, 2000, 'referência')
    if reference_url:
        URLValidator(schemes=['https', 'http'])(reference_url)
    character = None
    if character_id:
        character = TbPersonagem.objects.filter(pk=character_id).first()
        if character is None or (character.dono_id != actor.pk
                and not (can_review(actor, queue) and can(actor, 'people.view'))):
            raise PermissionDenied
    if queue in ('ficha', 'historia') and character is None:
        raise ValidationError('Selecione o personagem desta solicitação.')
    requester = actor
    if requester_id is not None and requester_id != actor.pk:
        if not (queue == 'ficha' and character and character.dono_id == requester_id
                and can(actor, 'people.view') and can_review(actor, queue)
                and (can(actor, 'characters.training') or can(actor, 'characters.profile'))):
            raise PermissionDenied
        requester = get_user_model().objects.get(pk=requester_id)
        if not requester.is_active:
            raise ValidationError('A conta do dono está inativa.')
    operation = _uuid(request_id)
    digest = _digest({'actor': actor.pk, 'queue': queue, 'title': title, 'description': description,
                      'url': reference_url, 'character': character.pk if character else None})
    if requester.pk != actor.pk:
        digest = _digest({'payload': digest, 'requester': requester.pk})
    # Serialize retries from the same requester, including a simultaneous double click.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    previous = PortalRequest.objects.filter(request_id=operation).first()
    if previous:
        if previous.requester_id != requester.pk or previous.payload_digest != digest:
            raise ValidationError('Operação já utilizada com outros dados.')
        return previous
    task = PortalRequest.objects.create(request_id=operation, payload_digest=digest,
        requester=requester, queue=queue, title=title, description=description,
        reference_url=reference_url, character=character)
    PortalActivity.objects.create(task=task, actor=actor, action='create', note=description,
                                  payload_digest=digest, after={'status': task.status, 'version': 1})
    return task


CHARACTER_CASES = {
    'training': ('characters.training', 'Treinamento comprovado'),
    'profile': ('characters.profile', 'Correção de dados da ficha'),
}


@transaction.atomic
def open_character_case(*, actor, character_id, purpose, request_id, reason):
    actor = _actor(actor)
    if purpose not in CHARACTER_CASES:
        raise ValidationError('Operação de ficha inválida.')
    capability, title = CHARACTER_CASES[purpose]
    if not (can(actor, 'people.view') and can(actor, capability) and can_review(actor, 'ficha')):
        raise PermissionDenied
    person = TbPersonagem.objects.select_related('dono').get(pk=character_id)
    if person.arquivado or not person.dono.is_active:
        raise ValidationError('Ficha arquivada ou conta do dono inativa.')
    operation = _uuid(request_id)
    task = create_request(actor=actor, request_id=operation, queue='ficha',
        title=(title + ': ' + person.nome)[:200], description=reason,
        character_id=person.pk, requester_id=person.dono_id)
    if task.status == 'new':
        task = act_on_request(actor=actor, task_id=task.pk,
            request_id=uuid5(operation, 'start-character-case'), version=task.version,
            action='start', note=reason)
    return task


@transaction.atomic
def act_on_request(*, actor, task_id, request_id, version, action, note, description=''):
    actor = _actor(actor)
    task = PortalRequest.objects.select_for_update().get(pk=task_id)
    if not visible_requests(actor).filter(pk=task.pk).exists():
        raise PermissionDenied
    operation = _uuid(request_id)
    note = _text(note, 8000, 'parecer ou comentário', 3)
    digest = _digest({'actor': actor.pk, 'task': task.pk, 'version': version,
                      'action': action, 'note': note, 'description': description})
    previous = PortalActivity.objects.filter(request_id=operation).first()
    if previous:
        if previous.actor_id != actor.pk or previous.task_id != task.pk or previous.payload_digest != digest:
            raise ValidationError('Operação já utilizada com outros dados.')
        return task
    if action not in allowed_actions(actor, task):
        raise PermissionDenied
    if version != task.version:
        raise ValidationError('A solicitação mudou. Recarregue e confira o histórico antes de enviar.')
    before = {'status': task.status, 'assignee': task.assignee_id, 'version': task.version}
    transitions = {'start': 'reviewing', 'return': 'waiting', 'finish': 'done',
                   'reject': 'rejected', 'resubmit': 'reviewing', 'reopen': 'reviewing'}
    if action in ('start', 'reopen'):
        task.assignee = actor
    if action == 'resubmit':
        before['description'] = task.description
        task.description = _text(description, 8000, 'descrição revisada', 5)
    task.status = transitions.get(action, task.status)
    task.version += 1
    task.save(update_fields=['status', 'version', 'assignee', 'description', 'updated_at'])
    PortalActivity.objects.create(request_id=operation, task=task, actor=actor,
        action=action, note=note, before=before, payload_digest=digest,
        after={'status': task.status, 'assignee': task.assignee_id, 'version': task.version})
    return task
