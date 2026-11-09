"""Version-bound submission and review; no approval inferred from an old story."""
import hashlib
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, F, OuterRef
from django.utils import timezone

from .character_story_models import CharacterStorySubmission
from .gestao.workflows import can_review
from .models import TbPersonagem

EDIT_SALT = 'bonfire.character-story.edit.v1'
REVIEW_SALT = 'bonfire.character-story.review.v1'


def digest(text):
    return hashlib.sha256((text or '').strip().encode('utf-8')).hexdigest()


def reviewer_allowed(user):
    return can_review(user, 'historia')


def pending_stories(actor):
    return CharacterStorySubmission.objects.filter(status='pending', character__arquivado=False,
        character__dono__is_active=True, author_id=F('character__dono_id')).exclude(author=actor)


def latest_submissions(user):
    newer = CharacterStorySubmission.objects.filter(character_id=OuterRef('character_id'), pk__gt=OuterRef('pk'))
    return CharacterStorySubmission.objects.filter(character__dono=user, author=user,
        character__arquivado=False).annotate(newer=Exists(newer)).filter(newer=False)


def notification_context(user):
    if not user.is_authenticated or not user.is_active:
        return {'pending_character_stories_count': 0, 'character_story_changes_count': 0}
    return {'pending_character_stories_count': pending_stories(user).count() if reviewer_allowed(user) else 0,
            'character_story_changes_count': latest_submissions(user).filter(status='changes').count()}


def _load(ticket, salt):
    try:
        return signing.loads(ticket, salt=salt, max_age=3600)
    except (signing.BadSignature, ValueError, TypeError):
        raise ValidationError('Página expirada ou inválida. Reabra antes de enviar.') from None


def _owner(actor, person):
    if (not actor.is_authenticated or not actor.is_active or person.dono_id != actor.pk
            or person.arquivado):
        raise PermissionDenied


def edit_ticket(actor, person):
    _owner(actor, person)
    return signing.dumps({'actor': actor.pk, 'character': person.pk,
        'base': digest(person.historia), 'request': str(uuid4())}, salt=EDIT_SALT)


@transaction.atomic
def save_story(*, actor, character_id, text, ticket, submit=False):
    person = TbPersonagem.objects.select_for_update().get(pk=character_id)
    actor = get_user_model().objects.get(pk=actor.pk)
    _owner(actor, person)
    data = _load(ticket, EDIT_SALT)
    if data.get('actor') != actor.pk or data.get('character') != person.pk:
        raise PermissionDenied
    if not isinstance(text, str) or len(text.strip()) > 5000 or '\x00' in text:
        raise ValidationError('Use uma história com até 5.000 caracteres.')
    text = text.strip()
    if submit and not text:
        raise ValidationError('Escreva a história antes de enviar à revisão.')
    previous = CharacterStorySubmission.objects.filter(request_id=data['request']).first()
    if previous:
        if previous.author_id != actor.pk or previous.character_id != person.pk or previous.text_digest != digest(text):
            raise ValidationError('Este envio já foi usado com outro texto.')
        return previous
    current = digest(person.historia)
    if current != data['base'] and not (not submit and current == digest(text)):
        raise ValidationError('A história mudou em outra janela. Reabra para não sobrescrever alterações.')
    if current != digest(text):
        person.historia = text or None
        person.save(update_fields=['historia', 'atualizado_em'])
    if not submit:
        return None
    pending = CharacterStorySubmission.objects.filter(character=person, status='pending').first()
    if pending and pending.author_id == actor.pk and pending.text_digest == digest(text):
        return pending
    if pending:
        pending.status = 'superseded'
        pending.save(update_fields=['status'])
    return CharacterStorySubmission.objects.create(request_id=data['request'], character=person,
        author=actor, text=text, text_digest=digest(text))


def review_ticket(actor, submission):
    if not reviewer_allowed(actor) or submission.author_id == actor.pk:
        raise PermissionDenied
    return signing.dumps({'actor': actor.pk, 'submission': submission.pk,
        'text': submission.text_digest, 'owner': submission.character.dono_id}, salt=REVIEW_SALT)


@transaction.atomic
def decide_story(*, actor, submission_id, action, feedback, ticket):
    if action not in ('approved', 'changes') or not isinstance(feedback, str):
        raise ValidationError('Decisão inválida.')
    feedback = feedback.strip()
    if len(feedback) > 3000 or '\x00' in feedback or (action == 'changes' and len(feedback) < 5):
        raise ValidationError('Para devolver, explique os ajustes (5 a 3.000 caracteres).')
    data = _load(ticket, REVIEW_SALT)
    # Lock in the same order as submission: character, then submitted revision.
    ref = CharacterStorySubmission.objects.only('character_id').get(pk=submission_id)
    person = TbPersonagem.objects.select_for_update().select_related('dono').get(pk=ref.character_id)
    submission = CharacterStorySubmission.objects.select_for_update().get(pk=submission_id)
    actor = get_user_model().objects.get(pk=actor.pk)
    if (not reviewer_allowed(actor) or submission.author_id == actor.pk
            or data.get('actor') != actor.pk or data.get('submission') != submission.pk
            or data.get('text') != submission.text_digest or data.get('owner') != person.dono_id
            or submission.author_id != person.dono_id or person.arquivado or not person.dono.is_active):
        raise PermissionDenied
    if submission.status != 'pending':
        if submission.status == action and submission.reviewer_id == actor.pk and submission.feedback == feedback:
            return submission
        raise ValidationError('Esta versão já foi revisada ou substituída. Reabra a fila.')
    if action == 'approved' and digest(person.historia) != submission.text_digest:
        raise ValidationError('O jogador alterou a história. Aguarde o reenvio; esta versão não pode ser aprovada.')
    submission.status, submission.feedback = action, feedback
    submission.reviewer, submission.reviewed_at = actor, timezone.now()
    submission.save(update_fields=['status', 'feedback', 'reviewer', 'reviewed_at'])
    return submission


def story_context(person):
    latest = person.story_submissions.select_related('reviewer').first()
    label = 'História ainda não enviada para aprovação' if person.historia else 'Sem história registrada'
    current = bool(latest and latest.author_id == person.dono_id and latest.text_digest == digest(person.historia))
    if latest:
        label = latest.get_status_display() if current else 'História alterada: falta enviar a nova versão'
    return {'latest': latest, 'current': current, 'label': label,
            'approved': bool(current and latest.status == 'approved')}
