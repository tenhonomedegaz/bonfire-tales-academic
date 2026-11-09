"""Apply an attested training through the portal without replaying a purchase."""
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from home.market_services import register_completed_training, training_catalog_entry
from home.models import TbPersonagem
from home.portal_models import PortalActivity, PortalRequest
from .policy import can
from .services import _digest
from .workflows import can_review

SALT = 'bonfire.management.completed-training.v1'


def can_register_training(actor, task):
    return bool(can(actor, 'characters.training') and can_review(actor, 'ficha')
                and task.queue == 'ficha' and task.character_id
                and task.status == 'reviewing' and task.assignee_id == actor.pk)


def _require(actor, task):
    if not can_register_training(actor, task):
        raise PermissionDenied


def _state(task, catalog, kind):
    person = task.character
    return _digest({
        'task': [task.pk, task.version, task.status, task.queue, task.assignee_id, task.character_id],
        'person': [person.pk, person.dono_id, person.arquivado, person.dono.is_active],
        'catalog': [kind, catalog.pk, catalog.nome],
        'proficiencies': list(person.proficiencias.order_by('pk').values_list('pk', 'tipo', 'nome', 'origem')),
        'training': list(person.treinamentos_mercado.order_by('pk').values_list(
            'pk', 'tipo', 'nome', 'status', 'conclui_em', 'concluido_em')),
    })


def preview_training(*, actor, task_id, token, reason, evidence, finish=False):
    task = PortalRequest.objects.select_related('character__dono').get(pk=task_id)
    _require(actor, task)
    reason = reason.strip() if isinstance(reason, str) else ''
    evidence = evidence.strip() if isinstance(evidence, str) else ''
    if not 5 <= len(reason) <= 500 or not 5 <= len(evidence) <= 2000:
        raise ValidationError('Informe o motivo e a evidência do treinamento já concluído.')
    kind, catalog = training_catalog_entry(token)
    if catalog is None:
        raise ValidationError('Selecione um idioma ou ferramenta do catálogo.')
    person = task.character
    if person.arquivado or not person.dono.is_active:
        raise ValidationError('A ficha está arquivada ou a conta do dono está inativa.')
    known = person.proficiencias.filter(tipo=kind, nome__iexact=catalog.nome).exists()
    if not known and person.treinamentos_mercado.filter(
            tipo=kind, nome__iexact=catalog.nome, status='ativo').exists():
        raise ValidationError('Há um treinamento pago em andamento para esta opção; ele não será alterado.')
    data = {'actor': actor.pk, 'task': task.pk, 'character': person.pk, 'token': token,
            'reason': reason, 'evidence': evidence, 'finish': bool(finish),
            'version': _state(task, catalog, kind), 'request_id': str(uuid4())}
    return {'task': task, 'person': person, 'name': catalog.nome, 'kind': kind,
            'already_known': known, 'reason': reason, 'evidence': evidence, 'finish': bool(finish),
            'ticket': signing.dumps(data, salt=SALT, compress=True)}


@transaction.atomic
def apply_training(*, actor, task_id, ticket):
    if not can(actor, 'characters.training') or not can_review(actor, 'ficha'):
        raise PermissionDenied
    try:
        data = signing.loads(ticket, salt=SALT, max_age=600)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError('Prévia inválida ou expirada. Confira novamente.') from None
    if data.get('actor') != actor.pk or data.get('task') != task_id:
        raise PermissionDenied
    actor = get_user_model().objects.select_for_update().get(pk=actor.pk)
    if not can(actor, 'characters.training') or not can_review(actor, 'ficha'):
        raise PermissionDenied
    task = PortalRequest.objects.select_for_update().get(pk=task_id)
    digest = _digest(data)
    receipt = PortalActivity.objects.filter(request_id=data['request_id']).first()
    if receipt:
        if receipt.actor_id != actor.pk or receipt.task_id != task.pk or receipt.payload_digest != digest:
            raise ValidationError('Identificador já usado em outra operação.')
        return receipt
    _require(actor, task)
    person = TbPersonagem.objects.select_for_update().select_related('dono').get(pk=task.character_id)
    task.character = person
    kind, catalog = training_catalog_entry(data['token'])
    if catalog is not None:
        catalog = type(catalog).objects.select_for_update().get(pk=catalog.pk)
    if catalog is None or _state(task, catalog, kind) != data['version']:
        raise ValidationError('A ficha, o catálogo ou o atendimento mudou. Gere outra prévia.')
    if data['character'] != person.pk or person.arquivado or not person.dono.is_active:
        raise ValidationError('A ficha não está disponível para esta operação.')
    before = {'status': task.status, 'version': task.version,
              'character': person.pk, 'training': {'kind': kind, 'name': catalog.nome}}
    proficiency, created = register_completed_training(person, data['token'])
    task.version += 1
    if data['finish']:
        task.status = 'done'
    task.save(update_fields=['version', 'status', 'updated_at'])
    return PortalActivity.objects.create(request_id=UUID(data['request_id']), task=task, actor=actor,
        action='training', note=data['reason'] + '\nEvidência: ' + data['evidence'],
        before=before, after={'status': task.status, 'version': task.version, 'character': person.pk,
            'proficiency': proficiency.pk, 'created': created, 'charged_pc': 0,
            'kind': kind, 'name': proficiency.nome}, payload_digest=digest)
