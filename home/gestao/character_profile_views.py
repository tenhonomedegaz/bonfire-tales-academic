from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from home.models import TbPersonagem
from home.portal_models import PortalRequest
from .character_profile import (PROFILE_FIELDS, TEXT_LIMITS, apply_profile,
    can_correct_profile, edit_token, preview_profile, profile_values)
from .policy import require_capability
from .requests import open_character_case
from .views import _workspace
from .workflows import can_review


class ProfileCaseForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Motivo do atendimento', min_length=5, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 3}))


class ProfileForm(forms.Form):
    base_token = forms.CharField(widget=forms.HiddenInput, max_length=4096)
    reason = forms.CharField(label='Motivo da correção', min_length=5, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 2}))
    evidence = forms.CharField(label='Evidência ou referência', min_length=5, max_length=2000,
                               widget=forms.Textarea(attrs={'rows': 3}))
    finish = forms.BooleanField(label='Concluir solicitação após aplicar a correção', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, label in PROFILE_FIELDS.items():
            field = TbPersonagem._meta.get_field(key)
            self.fields[key] = forms.CharField(label=label, required=key == 'nome',
                max_length=field.max_length or TEXT_LIMITS[key],
                widget=forms.Textarea(attrs={'rows': 4}) if key in TEXT_LIMITS else forms.TextInput)
        self.order_fields(['base_token', *PROFILE_FIELDS, 'reason', 'evidence', 'finish'])


class ProfileConfirmationForm(forms.Form):
    ticket = forms.CharField(widget=forms.HiddenInput, max_length=160000)


@never_cache
@require_capability('people.view')
@require_capability('characters.profile')
@require_http_methods(['GET', 'POST'])
def open_case(request, pk):
    if not can_review(request.user, 'ficha'):
        raise PermissionDenied
    person = get_object_or_404(TbPersonagem.objects.select_related('dono'),
                               pk=pk, arquivado=False, dono__is_active=True)
    form = ProfileCaseForm(request.POST if request.method == 'POST' else None,
                            initial={'request_id': uuid4()})
    if request.method == 'POST' and form.is_valid():
        try:
            task = open_character_case(actor=request.user, character_id=person.pk, purpose='profile',
                request_id=form.cleaned_data['request_id'], reason=form.cleaned_data['reason'])
            destination = ('gestao:request_profile' if can_correct_profile(request.user, task)
                           else 'gestao:request_detail')
            return redirect(destination, pk=task.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'home/gestao/profile_case.html', _workspace(request,
        'Corrigir dados da ficha', person=person, form=form))


@never_cache
@require_capability('characters.profile')
@require_http_methods(['GET', 'POST'])
def correct(request, pk):
    task = get_object_or_404(PortalRequest.objects.select_related('character__dono'), pk=pk)
    if not can_review(request.user, 'ficha') or task.queue != 'ficha' or not task.character_id:
        raise PermissionDenied
    confirming = request.method == 'POST' and request.POST.get('action') == 'confirm'
    if not confirming and not can_correct_profile(request.user, task):
        raise PermissionDenied
    initial = profile_values(task.character)
    if can_correct_profile(request.user, task):
        initial['base_token'] = edit_token(request.user, task)
    form = ProfileForm(initial=initial)
    confirmation = ProfileConfirmationForm()
    preview = None
    if request.method == 'POST':
        try:
            if confirming:
                confirmation = ProfileConfirmationForm(request.POST)
                if confirmation.is_valid():
                    apply_profile(actor=request.user, task_id=task.pk, ticket=confirmation.cleaned_data['ticket'])
                    messages.success(request, 'Correção aplicada e registrada no histórico.')
                    return redirect('gestao:request_detail', pk=task.pk)
            elif request.POST.get('action') == 'preview':
                form = ProfileForm(request.POST, initial=initial)
                if form.is_valid():
                    data = form.cleaned_data
                    preview = preview_profile(actor=request.user, task_id=task.pk,
                        base_token=data['base_token'], changes={key: data[key] for key in PROFILE_FIELDS},
                        reason=data['reason'], evidence=data['evidence'], finish=data['finish'])
                    confirmation = ProfileConfirmationForm(initial={'ticket': preview['ticket']})
            else:
                form.add_error(None, 'Ação inválida.')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'home/gestao/character_profile.html', _workspace(request,
        'Corrigir dados da ficha', management_section='requests', task=task, form=form,
        profile_fields=[form[key] for key in PROFILE_FIELDS], long_fields=TEXT_LIMITS,
        preview=preview, confirmation_form=confirmation))
