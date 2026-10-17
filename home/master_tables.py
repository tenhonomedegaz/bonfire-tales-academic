"""Moderated site listings; Discord quests, queues and MM remain authoritative."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .master_hub import (TableAnnouncementForm, apply_banner, can_review,
                         player_choices, selected_player_names, transition)
from .master_commercial import commercial_eligibility
from .models import TbMesaAnuncio, TbPerfilMestre
from .table_commerce import offer_summary


@login_required(login_url='/login/')
@require_http_methods(['GET', 'HEAD', 'POST'])
def table_edit(request, pk=None):
    if not TbPerfilMestre.objects.filter(user=request.user, status_mestre='aprovado').exists():
        raise PermissionDenied
    if request.method == 'POST':
        with transaction.atomic():
            profile = get_object_or_404(TbPerfilMestre.objects.select_for_update(),
                                        user=request.user, status_mestre='aprovado')
            table = (get_object_or_404(TbMesaAnuncio.objects.select_for_update(),
                                       pk=pk, mestre=request.user) if pk else
                     TbMesaAnuncio(mestre=request.user))
            form = TableAnnouncementForm(request.POST, request.FILES, instance=table,
                                         player_choices=player_choices())
            if form.is_valid():
                action = request.POST.get('acao', '')
                if action not in ('rascunho', 'enviar'):
                    raise PermissionDenied
                if pk and form.cleaned_data['revisao'] != table.revisao:
                    form.add_error(None, 'O anúncio mudou. Reabra a edição antes de salvar.')
                elif (action == 'enviar' and form.cleaned_data['modalidade'] == 'paga'
                      and not commercial_eligibility(request.user)['eligible']):
                    form.add_error(None, 'A vitrine paga exige autorização comercial e 3 mesas verificadas nos últimos 30 dias, incluindo 1 aberta. Você ainda pode salvar um rascunho ou anunciar uma mesa gratuita.')
                else:
                    saved = form.save(commit=False)
                    saved.mestre = profile.user
                    saved.estado = transition(table.estado, action)
                    saved.revisao += 1
                    saved.revisor = None
                    saved.revisado_em = None
                    saved.nota_revisao = ''
                    saved.preco_demonstrativo = True
                    apply_banner(saved, form)
                    saved.save()
                    return redirect(reverse('profile') + '?aba=mestre&salvo=1#minhas-missoes')
    else:
        table = (get_object_or_404(TbMesaAnuncio, pk=pk, mestre=request.user) if pk else
                 TbMesaAnuncio(mestre=request.user))
        form = TableAnnouncementForm(instance=table, player_choices=player_choices())
    return render(request, 'home/pages/master_table_form.html', {
        'table': table, 'table_form': form, 'page_title': 'Preparar anúncio', 'noindex': True})


@login_required(login_url='/login/')
@require_POST
def table_action(request, pk):
    action = request.POST.get('acao', '')
    reviewer = can_review(request.user)
    if action in ('aprovar', 'ajustes') and not reviewer:
        raise PermissionDenied
    if action not in ('aprovar', 'ajustes', 'encerrar'):
        raise PermissionDenied
    with transaction.atomic():
        query = TbMesaAnuncio.objects.select_for_update()
        if action == 'encerrar':
            query = query.filter(mestre=request.user)
        table = get_object_or_404(query, pk=pk)
        try:
            version = int(request.POST.get('revisao', '-1'))
        except ValueError:
            return HttpResponse('O anúncio mudou.', status=409)
        if version != table.revisao:
            return HttpResponse('O anúncio mudou.', status=409)
        if action == 'aprovar':
            if not TbPerfilMestre.objects.filter(user=table.mestre,
                    status_mestre='aprovado', user__is_active=True).exists():
                return HttpResponse('Mestre indisponível.', status=409)
            if table.modalidade == 'paga':
                if not table.preco_demonstrativo or not commercial_eligibility(table.mestre)['eligible']:
                    return HttpResponse('Os requisitos comerciais atuais não estão atendidos.', status=409)
            if not table.agenda_combinar and (table.data is None or table.data <= timezone.now()):
                return HttpResponse('A data da mesa deve ser futura.', status=409)
        try:
            table.estado = transition(table.estado, action, reviewer)
        except ValidationError as error:
            return HttpResponse(str(error), status=409)
        table.revisao += 1
        if action in ('aprovar', 'ajustes'):
            table.revisor = request.user
            table.revisado_em = timezone.now()
            table.nota_revisao = request.POST.get('nota', '').strip()[:500]
        table.save()
    return redirect(reverse('master_dashboard') + '?salvo=1#revisao' if reviewer else
                    reverse('profile') + '?aba=mestre#minhas-missoes')


def table_detail(request, pk):
    table = get_object_or_404(TbMesaAnuncio.objects.select_related('mestre'), pk=pk)
    owner = request.user.is_authenticated and request.user.pk == table.mestre_id
    reviewer = can_review(request.user)
    authorized = TbPerfilMestre.objects.filter(user=table.mestre,
        status_mestre='aprovado', user__is_active=True).exists()
    if (table.estado != 'publicado' or not authorized) and not owner and not reviewer:
        raise Http404
    if (table.modalidade == 'paga' and not owner and not reviewer
            and not commercial_eligibility(table.mestre)['eligible']):
        raise Http404
    try:
        offer = offer_summary(table)
    except ValidationError:
        if not owner and not reviewer:
            raise Http404
        offer = {'invalid': True}
    return render(request, 'home/pages/master_table_detail.html', {
        'table': table, 'page_title': table.titulo, 'owner': owner,
        'can_review': reviewer, 'offer': offer,
        'private_players': selected_player_names(table, player_choices()) if owner or reviewer else {},
        'noindex': table.estado != 'publicado'})
