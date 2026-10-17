"""Moderated site profiles for masters; Discord mission policy remains in the bot."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .models import TbMesaAnuncio, TbPerfilMestre
from .master_hub import can_review


def can_authorize(user):
    return bool(user.is_authenticated and user.is_active and (
        user.is_superuser or (user.is_staff and user.has_perm('home.autorizar_mestres'))))


def participation(profile):
    approved = profile is not None and profile.status_mestre == 'aprovado'
    mode = profile.modo if approved else 'jogador'
    return {
        'is_master': approved,
        'status_mestre': profile.status_mestre if profile else 'nenhum',
        'role_label': dict(TbPerfilMestre._meta.get_field('modo').choices)[mode],
        'nota_avaliacao': profile.nota_avaliacao if profile else '',
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
    search = request.GET.get('q', '').strip()[:120]
    profiles = TbPerfilMestre.objects.filter(
        status_mestre='aprovado', listado=True, user__is_active=True,
    ).select_related('user', 'user__profile')
    if search:
        profiles = profiles.filter(Q(user__username__icontains=search) |
                                   Q(estilo__icontains=search) |
                                   Q(apresentacao__icontains=search))
    masters = [{'user': item.user, 'community': participation(item),
                'portfolio_banner': item.banner_portfolio_url}
               for item in profiles.order_by('user__username')[:100]]
    return render(request, 'home/pages/master_directory.html', {
        'masters': masters, 'search': search, 'page_title': 'Mestres da comunidade'})


@login_required(login_url='/login/')
def master_dashboard(request):
    authorizer = can_authorize(request.user)
    reviewer = can_review(request.user)
    from .master_portfolio import can_review_work
    work_reviewer = can_review_work(request.user)
    if not authorizer and not reviewer and not work_reviewer:
        raise PermissionDenied
    requests = (TbPerfilMestre.objects.exclude(status_mestre='nenhum').select_related(
        'user').order_by('-solicitado_em')[:100] if authorizer else [])
    review_queue = (TbMesaAnuncio.objects.filter(estado='pendente').select_related(
        'mestre').order_by('-atualizado_em')[:100] if reviewer else [])
    return render(request, 'home/pages/master_dashboard.html', {
        'can_authorize': authorizer, 'can_review': reviewer,
        'can_review_work': work_reviewer,
        'master_requests': requests, 'review_queue': review_queue,
        'page_title': 'Permissões de mestre', 'notice': request.GET.get('salvo')})


@login_required(login_url='/login/')
@require_POST
def master_request(request):
    with transaction.atomic():
        profile, _ = TbPerfilMestre.objects.select_for_update().get_or_create(user=request.user)
        if profile.status_mestre in ('nenhum', 'recusado'):
            profile.status_mestre = 'pendente'
            profile.solicitado_em = timezone.now()
            profile.versao += 1
            profile.save(update_fields=['status_mestre', 'solicitado_em', 'versao', 'atualizado_em'])
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
