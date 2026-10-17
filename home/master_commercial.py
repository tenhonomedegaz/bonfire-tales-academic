"""Staff verified eligibility for demonstrative paid master listings."""

from datetime import timedelta

from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import TbAutorizacaoVitrine, TbAventuraMestre, TbPerfilMestre, TbVerificacaoMesa
from .master_participation import can_authorize


def commercial_eligibility(user, today=None):
    today = today or timezone.localdate()
    since = today - timedelta(days=29)
    if not getattr(user, 'pk', None) or not user.is_active:
        return dict(eligible=False, approved_master=False, admin_authorized=False,
                    completed_tables=0, open_tables=0, since=since)
    approved = TbPerfilMestre.objects.filter(user=user, status_mestre='aprovado').exists()
    authorized = TbAutorizacaoVitrine.objects.filter(user=user, autorizada=True).exists()
    evidence = TbVerificacaoMesa.objects.filter(
        validada=True, aventura__mestre=user,
        aventura__data__gte=since, aventura__data__lte=today,
    )
    total = evidence.count()
    open_count = evidence.filter(aberta=True).count()
    return dict(eligible=bool(approved and authorized and total >= 3 and open_count >= 1),
                approved_master=approved, admin_authorized=authorized,
                completed_tables=total, open_tables=open_count, since=since)


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
    if request.POST.get('confirmar') != 'sim' or request.POST.get('acao') not in ('validar', 'invalidar'):
        return HttpResponse('Confirme a decisão.', status=400)
    note = request.POST.get('observacao', '').strip()
    if not note or len(note) > 800:
        return HttpResponse('Registre a evidência da mesa.', status=400)
    with transaction.atomic():
        adventure = get_object_or_404(TbAventuraMestre.objects.select_for_update(), pk=pk)
        if adventure.mestre_id == request.user.pk:
            raise PermissionDenied
        if not adventure.data or adventure.data > timezone.localdate():
            return HttpResponse('A mesa ainda não ocorreu.', status=409)
        TbVerificacaoMesa.objects.update_or_create(
            aventura=adventure, defaults={
                'aberta': request.POST.get('aberta') == 'sim',
                'validada': request.POST['acao'] == 'validar',
                'observacao': note, 'validado_por': request.user,
            })
    return redirect(reverse('master_dashboard') + '?salvo=1#mesas-verificadas')


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
