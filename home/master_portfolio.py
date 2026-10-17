"""Moderated master portfolio; no Discord role, quest or payment side effects."""

import uuid

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .master_hub import safe_public_url, validate_banner
from .models import TbPerfilMestre, TbTrabalhoMestre


def can_review_work(user):
    return bool(user.is_authenticated and user.is_active and (
        user.is_superuser or (user.is_staff and user.has_perm('home.revisar_trabalho_mestre'))))


class WorkForm(forms.ModelForm):
    revisao = forms.IntegerField(widget=forms.HiddenInput, required=False, initial=0)
    imagem = forms.FileField(required=False, label='Imagem do trabalho',
                             widget=forms.FileInput(attrs={'accept': 'image/png,image/jpeg,image/webp,image/gif'}))
    remover_imagem = forms.BooleanField(required=False, label='Remover imagem')

    class Meta:
        model = TbTrabalhoMestre
        fields = ('titulo', 'categoria', 'descricao', 'texto', 'video_url')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revisao'].initial = self.instance.revisao

    def clean_imagem(self):
        image = self.cleaned_data.get('imagem')
        if image:
            validate_banner(image)
        return image

    def clean_video_url(self):
        value = self.cleaned_data.get('video_url', '')
        if value and not safe_public_url(value):
            raise ValidationError('Use um link HTTPS sem credenciais na URL.')
        return value

    def clean(self):
        data = super().clean()
        if not any((data.get('texto'), data.get('imagem'), data.get('video_url'),
                    self.instance.imagem_url if not data.get('remover_imagem') else '')):
            raise ValidationError('Inclua texto, imagem ou vídeo para apresentar o trabalho.')
        return data


def portfolio_context(user, profile, public=False):
    authorized = bool(profile and profile.status_mestre == 'aprovado' and user.is_active)
    if public:
        works = (TbTrabalhoMestre.objects.filter(mestre=user, estado='publicado')[:12]
                 if authorized and profile.listado else [])
        return {'portfolio_cards': [{'item': work} for work in works]}
    return {'my_works': list(TbTrabalhoMestre.objects.filter(mestre=user)[:100])}


@login_required(login_url='/login/')
def gallery(request):
    profile = TbPerfilMestre.objects.filter(user=request.user).first()
    if not profile:
        raise PermissionDenied
    return render(request, 'home/pages/master_gallery.html', {
        'works': TbTrabalhoMestre.objects.filter(mestre=request.user)[:100],
        'can_edit': profile.status_mestre == 'aprovado' and request.user.is_active,
        'page_title': 'Galeria de mestre', 'noindex': True})


@login_required(login_url='/login/')
@require_http_methods(['GET', 'HEAD', 'POST'])
def work_edit(request, pk=None):
    if not TbPerfilMestre.objects.filter(user=request.user, status_mestre='aprovado').exists():
        raise PermissionDenied
    if request.method == 'POST':
        with transaction.atomic():
            profile = get_object_or_404(TbPerfilMestre.objects.select_for_update(), user=request.user)
            if profile.status_mestre != 'aprovado':
                raise PermissionDenied
            work = (get_object_or_404(TbTrabalhoMestre.objects.select_for_update(),
                                      pk=pk, mestre=request.user) if pk else
                    TbTrabalhoMestre(mestre=request.user))
            form = WorkForm(request.POST, request.FILES, instance=work)
            if form.is_valid():
                action = request.POST.get('acao')
                if action not in ('rascunho', 'enviar'):
                    raise PermissionDenied
                if form.cleaned_data['revisao'] != work.revisao:
                    form.add_error(None, 'O trabalho mudou. Atualize a página antes de salvar.')
                else:
                    saved = form.save(commit=False)
                    saved.mestre = request.user
                    saved.estado = 'pendente' if action == 'enviar' else 'rascunho'
                    saved.revisao += 1
                    saved.revisor = None
                    saved.revisado_em = None
                    saved.nota_revisao = ''
                    image = form.cleaned_data.get('imagem')
                    if image:
                        extension = validate_banner(image)
                        name = default_storage.save(
                            f'master_work/{request.user.pk}/{uuid.uuid4().hex}.{extension}', image)
                        saved.imagem_url = default_storage.url(name)
                    elif form.cleaned_data.get('remover_imagem'):
                        saved.imagem_url = ''
                    saved.save()
                    return redirect(reverse('master_gallery') + '?salvo=1')
    else:
        work = (get_object_or_404(TbTrabalhoMestre, pk=pk, mestre=request.user)
                if pk else TbTrabalhoMestre(mestre=request.user))
        form = WorkForm(instance=work)
    return render(request, 'home/pages/master_work_form.html', {
        'work': work, 'work_form': form, 'page_title': 'Trabalho do mestre', 'noindex': True})


@login_required(login_url='/login/')
def review_queue(request):
    if not can_review_work(request.user):
        raise PermissionDenied
    return render(request, 'home/pages/master_gallery_review.html', {
        'works': TbTrabalhoMestre.objects.filter(estado='pendente').select_related('mestre')[:100],
        'page_title': 'Revisar galeria', 'noindex': True})


@login_required(login_url='/login/')
@require_POST
def work_review(request, pk):
    if not can_review_work(request.user):
        raise PermissionDenied
    action = request.POST.get('acao')
    if action not in ('aprovar', 'ajustes'):
        raise PermissionDenied
    with transaction.atomic():
        work = get_object_or_404(TbTrabalhoMestre.objects.select_for_update(), pk=pk)
        try:
            version = int(request.POST.get('revisao', '-1'))
        except ValueError:
            return HttpResponse(status=409)
        if (version != work.revisao or work.estado != 'pendente' or
                work.mestre_id == request.user.pk):
            return HttpResponse('Revisão indisponível ou alterada.', status=409)
        if action == 'aprovar' and not TbPerfilMestre.objects.filter(
                user=work.mestre, status_mestre='aprovado', user__is_active=True).exists():
            return HttpResponse('Mestre indisponível.', status=409)
        work.estado = 'publicado' if action == 'aprovar' else 'ajustes'
        work.revisao += 1
        work.revisor = request.user
        work.revisado_em = timezone.now()
        work.nota_revisao = request.POST.get('nota', '').strip()[:500]
        work.save()
    return redirect(reverse('master_gallery_review'))


def work_detail(request, pk):
    work = get_object_or_404(TbTrabalhoMestre.objects.select_related('mestre'), pk=pk)
    owner = request.user.is_authenticated and request.user.pk == work.mestre_id
    reviewer = can_review_work(request.user)
    if not owner and not reviewer:
        visible = (work.estado == 'publicado' and
                   TbPerfilMestre.objects.filter(user=work.mestre, status_mestre='aprovado',
                                                 listado=True, user__is_active=True).exists())
        if not visible:
            raise Http404
    return render(request, 'home/pages/master_work_detail.html', {
        'work': work, 'work_owner': owner, 'work_video': bool(work.video_url),
        'page_title': work.titulo, 'noindex': work.estado != 'publicado'})
