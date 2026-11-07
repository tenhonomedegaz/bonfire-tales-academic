"""Public profile walls. Text stays untrusted markdown, never pre-rendered HTML.

Integrate with ``**wall_context(user, viewer, page, request=request)``. The optional
request consumes one bounded PRG draft; ordinary wall reads never write to the DB.
"""

import json
import re
from datetime import timedelta
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from . import cosmetics, permissions, social
from .cosmetic_packages import load_package
from .editorial_links import safe_editorial_image
from .models import (CosmeticCheckoutPurchase, CosmeticMMRedemption, EventCosmeticRedemption,
                     TbPerfilComentario, TbPerfilComentarioCurtida, TbUsuarioCosmetico)


COMMENT_LIMIT = 5
COMMENT_WINDOW = timedelta(minutes=10)
_DRAFT_KEY = 'profile_wall_draft'
_FRAME_KEY = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
_CLASS = re.compile(r'[A-Za-z_][A-Za-z0-9_-]*')


class ProfileCommentForm(forms.Form):
    texto = forms.CharField(max_length=4000, strip=True, widget=forms.Textarea(attrs={'maxlength': 4000}))
    chave_operacao = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)


def _active(user):
    return bool(getattr(user, 'pk', None) and getattr(user, 'is_authenticated', False)
                and getattr(user, 'is_active', False))


def _can_remove(comment, viewer):
    return _active(viewer) and (viewer.pk in (comment.autor_id, comment.perfil_id)
                                or permissions.is_staff_user(viewer))


def _public_comments():
    return TbPerfilComentario.objects.filter(
        removido_em__isnull=True, autor__is_active=True, perfil__is_active=True)


def _colab_tiers(users):
    """Batch the same OAuth-linked proof and tier ordering as permissions.colab_tier."""
    from .models import BotMember, BotTransaction
    discord = {user.pk: str(getattr(getattr(user, 'profile', None), 'discord_user_id', '') or '').strip()
               for user in users}
    discord = {pk: did for pk, did in discord.items() if did}
    if not discord:
        return {}
    try:
        with transaction.atomic():
            emails = {}
            for did, email in BotMember.objects.filter(discordUserId__in=set(discord.values())).order_by('pk').values_list(
                    'discordUserId', 'email'):
                emails.setdefault(str(did), (email or '').strip().lower())
            linked = {pk: emails[did] for pk, did in discord.items() if emails.get(did)}
            if not linked:
                return {}
            query = Q()
            for email in set(linked.values()):
                query |= Q(email__iexact=email)
            ranks = {}
            for email, plan in BotTransaction.objects.filter(
                    query, status=1, expirationDate__gt=timezone.now(),
                    subscriptionPlan__startswith='colaborador-').values_list('email', 'subscriptionPlan'):
                rank = permissions.COLAB_TIER_RANK.get(str(plan).split('-')[1], 0)
                email = (email or '').strip().lower()
                ranks[email] = max(rank, ranks.get(email, 0))
            tiers = {rank: name for name, rank in permissions.COLAB_TIER_RANK.items()}
            return {pk: tiers.get(ranks.get(email, 0)) for pk, email in linked.items()}
    except DatabaseError:
        return {}


def _frame_rights(users, slugs):
    """Batch only persisted rights; never cosmetic_allowed or rank read-repair."""
    ids = [user.pk for user in users]
    rights = {pk: set() for pk in ids}
    inventory = TbUsuarioCosmetico.objects.filter(
        user_id__in=ids, cosmetico__slug__in=slugs, suspenso_em__isnull=True,
    ).exclude(origem__startswith='colaborador').values_list('user_id', 'cosmetico__slug')
    paid = CosmeticCheckoutPurchase.objects.filter(
        beneficiary_id__in=ids, cosmetico__slug__in=slugs, granted_at__isnull=False,
    ).values_list('beneficiary_id', 'cosmetico__slug')
    events = EventCosmeticRedemption.objects.filter(
        user_id__in=ids, cosmetico__slug__in=slugs).values_list('user_id', 'cosmetico__slug')
    mm = CosmeticMMRedemption.objects.filter(
        user_id__in=ids, cosmetico__slug__in=slugs, reversed_at__isnull=True,
    ).values_list('user_id', 'cosmetico__slug')
    for rows in (inventory, paid, events, mm):
        for pk, slug in rows:
            rights[pk].add(slug)
    return rights


def _author_appearances(users):
    """Small avatar-only projection of the existing public cosmetic rules, in batches."""
    from .conquistas import visibilidade_conquistas_de_personagem
    users = list(users)
    if not users:
        return {}
    catalog = cosmetics.get_catalog('moldura')
    chosen = {user.pk: (getattr(getattr(user, 'profile', None), 'avatar_frame', '') or '').strip()
              for user in users}
    items = {pk: catalog.get(key) for pk, key in chosen.items()
             if len(key) <= 100 and _FRAME_KEY.fullmatch(key)}
    restricted = {pk: item for pk, item in items.items() if item and item.get('origem') != 'livre'}
    rights = _frame_rights(users, {item['slug'] for item in restricted.values()}) if restricted else {}
    hidden = visibilidade_conquistas_de_personagem(users)[1] if restricted else {}
    colab_users = [user for user in users if restricted.get(user.pk, {}).get('origem') == 'colaborador']
    tiers = _colab_tiers(colab_users) if colab_users else {}
    packages = {}
    result = {}
    for user in users:
        key = chosen[user.pk]
        item = items.get(user.pk)
        private = hidden.get(user.pk, set())
        allowed = (item and cosmetics._scope_ok(item, 'perfil') and key not in private
                   and item['slug'] not in private and (item['origem'] == 'livre'
                   or item['slug'] in rights.get(user.pk, set())
                   or cosmetics._colab_allows(item, tiers.get(user.pk))))
        if not allowed:
            key, item = 'none', {}
        tokens = (item.get('class') or '').split()
        frame_class = ' '.join(tokens) if all(_CLASS.fullmatch(token) for token in tokens) else ''
        if key not in packages:
            packages[key] = load_package('moldura', key, 'perfil') if allowed and key != 'none' else None
        result[user.pk] = {
            'avatar_url': safe_editorial_image(getattr(getattr(user, 'profile', None), 'avatar_url', '')),
            'frame_key': key, 'frame_class': frame_class, 'frame_package': packages[key],
        }
    return result


def wall_context(viewed_user, viewer, page_number=1, *, request=None):
    """Return {'profile_wall': {...}}; rows are dictionaries, raw texto is not safe HTML."""
    active_wall = bool(getattr(viewed_user, 'pk', None) and getattr(viewed_user, 'is_active', False))
    can_comment = active_wall and _active(viewer)
    comments = _public_comments().filter(perfil=viewed_user) if active_wall else TbPerfilComentario.objects.none()
    liked = TbPerfilComentarioCurtida.objects.filter(comentario_id=OuterRef('pk'), quem_id=viewer.pk) if _active(
        viewer) else TbPerfilComentarioCurtida.objects.none()
    comments = comments.select_related('autor__profile').annotate(
        like_count=Count('curtidas', filter=Q(curtidas__quem__is_active=True)),
        liked_by_viewer=Exists(liked)).order_by('-criado_em', '-pk')
    page = Paginator(comments, 10).get_page(page_number)
    objects = list(page.object_list)
    authors = {comment.autor_id: comment.autor for comment in objects}
    with cosmetics.cosmetic_read_context():
        appearances = _author_appearances(authors.values())
    page.object_list = [dict(
        obj=comment, pk=comment.pk, texto=comment.texto, autor=comment.autor, criado_em=comment.criado_em,
        like_count=comment.like_count, liked_by_viewer=comment.liked_by_viewer,
        can_remove=_can_remove(comment, viewer),
        can_like=_active(viewer) and social.pode_interagir(viewer, comment.autor),
        appearance=appearances[comment.autor_id], **appearances[comment.autor_id],
    ) for comment in objects]
    form = ProfileCommentForm() if can_comment else None
    if request is not None and can_comment:
        draft = request.session.get(_DRAFT_KEY)
        if (isinstance(draft, dict) and draft.get('perfil_id') == viewed_user.pk
                and draft.get('autor_id') == viewer.pk):
            request.session.pop(_DRAFT_KEY)
            form = ProfileCommentForm(data={
                'texto': str(draft.get('texto', ''))[:4000],
                'chave_operacao': draft.get('chave_operacao') or str(uuid4()),
            })
            form.is_valid()
            if draft.get('error'):
                form.add_error(None, str(draft['error'])[:300])
    return {'profile_wall': {'comments_page': page, 'comment_form': form, 'can_comment': can_comment}}


def _wall_redirect(username):
    return redirect(reverse('public_profile', kwargs={'username': username}) + '#comentarios')


def _create_error(request, target, text, error):
    request.session[_DRAFT_KEY] = {
        'perfil_id': target.pk, 'autor_id': request.user.pk, 'texto': text[:4000],
        'chave_operacao': str(uuid4()), 'error': error[:300],
    }
    messages.error(request, error)
    return _wall_redirect(target.username)


@never_cache
@login_required
@require_POST
@csrf_protect
def comment_create(request, username):
    if not _active(request.user):
        return HttpResponseForbidden()
    target = get_object_or_404(get_user_model(), username__iexact=username, is_active=True)
    form = ProfileCommentForm(request.POST)
    if not form.is_valid():
        return _create_error(request, target, request.POST.get('texto', ''),
                             'Informe um texto de 1 a 4000 caracteres e um identificador de envio valido.')
    text, key = form.cleaned_data['texto'], form.cleaned_data['chave_operacao']
    with transaction.atomic():
        # Serialize this author without blocking FK checks on reciprocal wall posts.
        actor = get_object_or_404(get_user_model().objects.select_for_update(no_key=True),
                                  pk=request.user.pk, is_active=True)
        previous = TbPerfilComentario.objects.filter(chave_operacao=key).first()
        if previous:
            if previous.autor_id != actor.pk or previous.perfil_id != target.pk or previous.texto != text:
                return _create_error(request, target, text, 'Identificador de envio ja utilizado para outro comentario.')
        else:
            # Count deleted comments too: deleting must not reset the author's spam window.
            if TbPerfilComentario.objects.filter(
                    autor=actor, criado_em__gte=timezone.now() - COMMENT_WINDOW).count() >= COMMENT_LIMIT:
                return _create_error(request, target, text, 'Limite temporario de comentarios atingido. Tente mais tarde.')
            previous, created = TbPerfilComentario.objects.get_or_create(
                chave_operacao=key, defaults={'perfil': target, 'autor': actor, 'texto': text})
            if not created and (previous.autor_id != actor.pk or previous.perfil_id != target.pk or previous.texto != text):
                return _create_error(request, target, text, 'Identificador de envio ja utilizado para outro comentario.')
    draft = request.session.get(_DRAFT_KEY)
    if isinstance(draft, dict) and draft.get('perfil_id') == target.pk and draft.get('autor_id') == request.user.pk:
        request.session.pop(_DRAFT_KEY)
    return _wall_redirect(target.username)


def _like_error(request, comment, error, status=400):
    if request.content_type == 'application/json':
        return JsonResponse({'ok': False, 'error': error}, status=status)
    messages.error(request, error)
    return _wall_redirect(comment.perfil.username)


@never_cache
@login_required
@require_POST
@csrf_protect
def comment_like(request, comment_id):
    if not _active(request.user):
        return HttpResponseForbidden()
    with transaction.atomic():
        comment = get_object_or_404(_public_comments().select_for_update(of=('self',)).select_related(
            'autor', 'perfil'), pk=comment_id)
        if not social.pode_interagir(request.user, comment.autor):
            return _like_error(request, comment, 'Voce nao pode curtir seu proprio comentario.')
        desired = request.POST.get('curtido')
        is_json = request.content_type == 'application/json'
        if is_json:
            try:
                data = json.loads(request.body) if len(request.body) <= 1024 else None
            except (ValueError, UnicodeError):
                data = None
            desired = data.get('curtido') if isinstance(data, dict) else None
        elif desired in ('true', 'false'):
            desired = desired == 'true'
        if type(desired) is not bool:
            return _like_error(request, comment, 'Informe curtido como true ou false.')
        if desired:
            TbPerfilComentarioCurtida.objects.get_or_create(comentario=comment, quem=request.user)
        else:
            TbPerfilComentarioCurtida.objects.filter(comentario=comment, quem=request.user).delete()
        total = TbPerfilComentarioCurtida.objects.filter(comentario=comment, quem__is_active=True).count()
    if is_json:
        return JsonResponse({'ok': True, 'curtido': desired, 'curtidas': total})
    return _wall_redirect(comment.perfil.username)


@never_cache
@login_required
@require_POST
@csrf_protect
def comment_remove(request, comment_id):
    if not _active(request.user):
        return HttpResponseForbidden()
    with transaction.atomic():
        comment = get_object_or_404(TbPerfilComentario.objects.select_for_update(of=('self',)).select_related(
            'perfil'), pk=comment_id)
        if not _can_remove(comment, request.user):
            return HttpResponseForbidden()
        TbPerfilComentario.objects.filter(pk=comment.pk, removido_em__isnull=True).update(
            removido_em=timezone.now(), removido_por=request.user)
    return _wall_redirect(comment.perfil.username)
