"""Recorded mission activity and separate authorization for paid demonstrations."""

from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import TbAutorizacaoVitrine, TbPerfilMestre
from .master_participation import can_authorize


def completed_activity(user, today):
    from .master_roster import identities, mission_history
    since = today - timedelta(days=29)
    sessions, unavailable = {}, False
    # Use the latest identity snapshot for each Fogueira, as in the public directory.
    roster = {}
    for identity in identities().filter(user=user):
        roster.setdefault(identity.numero, identity)
    for identity in roster.values():
        rows, failed = mission_history(identity)
        unavailable |= failed
        for row in rows:
            day = row['completed_date']
            if row['completed'] and day and since <= day <= today:
                sessions.setdefault(row['session_key'], row)
    return {'completed_tables': len(sessions),
            'open_tables': sum(row['open_table'] for row in sessions.values()),
            'system_tables': sum(row['entry_origin'] == 'system' for row in sessions.values()),
            'manual_tables': sum(row['entry_origin'] == 'manual' for row in sessions.values()),
            'activity_unavailable': unavailable}


def commercial_eligibility(user, today=None):
    today = today or timezone.localdate()
    since = today - timedelta(days=29)
    if not getattr(user, 'pk', None) or not user.is_active:
        return dict(eligible=False, approved_master=False, admin_authorized=False,
                    completed_tables=0, open_tables=0, system_tables=0, manual_tables=0,
                    activity_unavailable=False, since=since)
    approved = TbPerfilMestre.objects.filter(user=user, status_mestre='aprovado').exists()
    authorized = TbAutorizacaoVitrine.objects.filter(user=user, autorizada=True).exists()
    activity = completed_activity(user, today)
    return dict(eligible=bool(approved and authorized and not activity['activity_unavailable']
                             and activity['completed_tables'] >= 3 and activity['open_tables'] >= 1),
                approved_master=approved, admin_authorized=authorized,
                **activity, since=since)


def visible_public_tables(tables):
    """Hide paid demonstrations immediately if current authorization lapses."""
    eligible_by_master = {}
    visible = []
    for table in tables:
        if table.modalidade == 'paga':
            if table.mestre_id not in eligible_by_master:
                eligible_by_master[table.mestre_id] = commercial_eligibility(table.mestre)['eligible']
            if not eligible_by_master[table.mestre_id]:
                continue
        visible.append(table)
    return visible


@login_required(login_url='/login/')
@require_POST
def verify_table(request, pk):
    if not can_authorize(request.user):
        raise PermissionDenied
    return HttpResponse('A verificação manual de realização foi encerrada. '
                        'Consulte o registro da missão no portfólio do mestre.', status=410)


@login_required(login_url='/login/')
@require_POST
def authorize_listing(request, pk):
    if not can_authorize(request.user):
        raise PermissionDenied
    if request.POST.get('confirmar') != 'sim' or request.POST.get('acao') not in ('autorizar', 'revogar'):
        return HttpResponse('Confirme a decisão.', status=400)
    note = request.POST.get('observacao', '').strip()
    if not note or len(note) > 800:
        return HttpResponse('Registre o motivo da decisão.', status=400)
    with transaction.atomic():
        profile = get_object_or_404(TbPerfilMestre.objects.select_for_update().select_related('user'), user_id=pk)
        if profile.user_id == request.user.pk:
            raise PermissionDenied
        if request.POST['acao'] == 'autorizar' and (profile.status_mestre != 'aprovado' or not profile.user.is_active):
            return HttpResponse('Mestre sem autorização vigente.', status=409)
        TbAutorizacaoVitrine.objects.update_or_create(
            user=profile.user, defaults={
                'autorizada': request.POST['acao'] == 'autorizar',
                'observacao': note, 'avaliado_por': request.user,
            })
    return redirect(reverse('master_dashboard') + '?salvo=1#vitrine-comercial')
