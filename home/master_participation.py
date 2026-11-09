"""Moderated site profiles for masters; Discord mission policy remains in the bot."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.cache import never_cache

from .models import TbMesaAnuncio, TbPerfilMestre
from .master_hub import can_review
from .master_registration import applications_open, roster_for


def can_authorize(user):
    from .master_hub import can_authorize as authorized
    return authorized(user)


def participation(profile):
    approved = profile is not None and profile.status_mestre == 'aprovado'
    mode = profile.modo if approved else 'jogador'
    return {
        'is_master': approved,
        'applications_open': applications_open(),
        'status_mestre': profile.status_mestre if profile else 'nenhum',
        'role_label': dict(TbPerfilMestre._meta.get_field('modo').choices)[mode],
        'nota_avaliacao': profile.nota_avaliacao if profile else '',
        'solicitado_em': profile.solicitado_em if profile else None,
        'modo': mode,
        'listado': bool(approved and profile.listado),
        'estilo': profile.estilo if approved else '',
        'apresentacao': profile.apresentacao if approved else '',
        'disponibilidade': profile.disponibilidade if approved else '',
    }


class ParticipationForm(forms.ModelForm):
    class Meta:
        model = TbPerfilMestre
        fields = ('modo', 'apresentacao', 'estilo', 'disponibilidade',
                  'experiencia', 'combinados', 'listado')
        widgets = {'modo': forms.RadioSelect}

    def clean_modo(self):
        mode = self.cleaned_data['modo']
        if mode not in ('mestre', 'ambos'):
            raise forms.ValidationError('Escolha como participar como mestre.')
        return mode


def masters_directory(request):
    from .master_roster import directory
    return directory(request)


@login_required(login_url='/login/')
@never_cache
def master_dashboard(request):
    authorizer = can_authorize(request.user)
    reviewer = can_review(request.user)
    from .master_portfolio import can_review_work
    work_reviewer = can_review_work(request.user)
    if not authorizer and not reviewer and not work_reviewer:
        raise PermissionDenied
    status_choices = [(value, label) for value, label in
                      TbPerfilMestre._meta.get_field('status_mestre').choices
                      if value != 'nenhum'] + [('todos', 'Todos')]
    request_status = request.GET.get('permissao', 'pendente')
    if request_status not in dict(status_choices):
        request_status = 'pendente'
    request_search = request.GET.get('solicitante', '').strip()[:120]
    requests_page, pending_count = None, 0
    if authorizer:
        requests = TbPerfilMestre.objects.exclude(status_mestre='nenhum').select_related('user')
        pending_count = requests.filter(status_mestre='pendente').count()
        if request_status != 'todos':
            requests = requests.filter(status_mestre=request_status)
        if request_search:
            requests = requests.filter(user__username__icontains=request_search)
        ordering = ('solicitado_em', 'pk') if request_status == 'pendente' else ('-solicitado_em', '-pk')
        requests_page = Paginator(requests.order_by(*ordering), 25).get_page(request.GET.get('solicitacoes_pagina'))
    requests = list(requests_page.object_list) if requests_page else []
    from .models import TbMestreLegado
    identities = list(TbMestreLegado.objects.filter(user_id__in=[p.user_id for p in requests]))
    for applicant in requests:
        from .master_application import application_answers
        applicant.candidatura_respostas = application_answers(applicant.candidatura_json)
        applicant.fogueiras = [f'F{identity.numero:02d}' for identity in identities
                               if identity.user_id == applicant.user_id]
        applicant.portfolio_links = [{'label': f'F{identity.numero:02d}',
            'url': reverse('master_roster_portfolio', args=[identity.numero])}
            for identity in identities if identity.user_id == applicant.user_id]
    from .gestao.editorial_views import review_page
    review_queue, review_pagination = (review_page(request, TbMesaAnuncio.objects.filter(
        estado='pendente').select_related('mestre').order_by('atualizado_em', 'pk'),
        item_parameter='anuncio', page_parameter='anuncios_pagina') if reviewer else ([], {}))
    commercial_masters = (Paginator(TbPerfilMestre.objects.filter(
        status_mestre='aprovado', user__is_active=True).exclude(user=request.user).select_related(
        'user', 'user__autorizacao_vitrine').order_by('user__username', 'pk'), 25).get_page(
        request.GET.get('vitrine_pagina')) if authorizer else [])
    from .gestao.views import _workspace
    return render(request, 'home/pages/master_dashboard.html', _workspace(request, 'Mestres e divulgação',
        management_section='masters', **{
        'can_authorize': authorizer, 'can_review': reviewer,
        'can_review_work': work_reviewer,
        'master_requests': requests, 'review_queue': review_queue,
        'master_requests_page': requests_page, 'pending_master_count': pending_count,
        'announcements_previous_url': review_pagination.get('previous_url', ''),
        'announcements_next_url': review_pagination.get('next_url', ''),
        'master_applications_open': applications_open(),
        'request_status': request_status, 'request_status_options': status_choices,
        'request_search': request_search,
        'commercial_masters': commercial_masters,
        'notice': request.GET.get('salvo')}))


@login_required(login_url='/login/')
@require_http_methods(['GET', 'POST'])
def master_request(request):
    if not applications_open():
        return HttpResponse('Novas solicitacoes de mestre estao temporariamente encerradas.', status=403)
    from .master_application import MasterApplicationForm
    form = MasterApplicationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'GET' or not form.is_valid():
        return render(request, 'home/pages/master_application.html', {'application_form': form},
                      status=400 if request.method == 'POST' else 200)
    with transaction.atomic():
        profile, _ = TbPerfilMestre.objects.select_for_update().get_or_create(user=request.user)
        if profile.status_mestre in ('nenhum', 'recusado'):
            profile.status_mestre = 'pendente'
            profile.solicitado_em = timezone.now()
            profile.candidatura_json = form.snapshot()
            profile.versao += 1
            profile.save(update_fields=['status_mestre', 'solicitado_em', 'candidatura_json', 'versao', 'atualizado_em'])
    return redirect(reverse('profile') + '?aba=mestre#perfil-mestre')


@login_required(login_url='/login/')
@require_POST
def master_authorize(request, pk):
    if not can_authorize(request.user):
        raise PermissionDenied
    action = request.POST.get('acao')
    if action not in ('autorizar', 'recusar', 'suspender') or request.POST.get('confirmar') != 'sim':
        return HttpResponse('Confirme explicitamente a alteração.', status=400)
    with transaction.atomic():
        profile = get_object_or_404(TbPerfilMestre.objects.select_for_update(), user_id=pk)
        try:
            version = int(request.POST.get('versao', '-1'))
        except ValueError:
            return HttpResponse(status=409)
        if version != profile.versao:
            return HttpResponse('Solicitação alterada. Atualize a página.', status=409)
        allowed = {'autorizar': ('pendente', 'recusado', 'suspenso'),
                   'recusar': ('pendente',), 'suspender': ('aprovado',)}
        if profile.status_mestre not in allowed[action] or not profile.user.is_active:
            return HttpResponse('Transição indisponível.', status=409)
        if action == 'autorizar' and not roster_for(profile.user_id).exists():
            return HttpResponse('Vincule primeiro a conta a uma Fogueira do cadastro vigente.', status=409)
        profile.status_mestre = {'autorizar': 'aprovado', 'recusar': 'recusado',
                                 'suspender': 'suspenso'}[action]
        profile.avaliador = request.user
        profile.avaliado_em = timezone.now()
        profile.nota_avaliacao = request.POST.get('nota', '').strip()[:500]
        profile.versao += 1
        profile.save(update_fields=['status_mestre', 'avaliador', 'avaliado_em',
                                    'nota_avaliacao', 'versao', 'atualizado_em'])
    return redirect(reverse('master_dashboard') + '?salvo=1#permissoes')


@login_required(login_url='/login/')
@require_http_methods(['GET', 'HEAD', 'POST'])
def participation_edit(request):
    profile = TbPerfilMestre.objects.filter(user=request.user).first()
    if profile is None or profile.status_mestre != 'aprovado':
        raise PermissionDenied
    form = ParticipationForm(request.POST if request.method == 'POST' else None,
                             instance=profile)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked = get_object_or_404(TbPerfilMestre.objects.select_for_update(), user=request.user)
            if locked.status_mestre != 'aprovado':
                raise PermissionDenied
            for name in form.Meta.fields:
                setattr(locked, name, form.cleaned_data[name])
            locked.versao += 1
            locked.save()
        return redirect(reverse('profile') + '?aba=mestre#perfil-mestre')
    return render(request, 'home/pages/master_profile_form.html', {
        'participation_form': form, 'community': participation(profile),
        'page_title': 'Sua participação'})
