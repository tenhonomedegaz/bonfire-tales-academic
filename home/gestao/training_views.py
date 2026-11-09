from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from home.portal_models import PortalRequest
from home.models import TbPersonagem
from .forms import GrantConfirmationForm
from .policy import require_capability
from .training import _require, apply_training, preview_training
from .views import _workspace
from .workflows import can_review
from .requests import open_character_case


class TrainingCaseForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Motivo da regularização', min_length=5, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 3}))


@never_cache
@require_capability('people.view')
@require_capability('characters.training')
@require_http_methods(['GET', 'POST'])
def open_case(request, pk):
    if not can_review(request.user, 'ficha'):
        raise PermissionDenied
    person = get_object_or_404(TbPersonagem.objects.select_related('dono'),
                               pk=pk, arquivado=False, dono__is_active=True)
    form = TrainingCaseForm(request.POST if request.method == 'POST' else None,
                             initial={'request_id': uuid4()})
    if request.method == 'POST' and form.is_valid():
        try:
            task = open_character_case(actor=request.user, character_id=person.pk, purpose='training',
                request_id=form.cleaned_data['request_id'], reason=form.cleaned_data['reason'])
            if task.status != 'reviewing' or task.assignee_id != request.user.pk:
                return redirect('gestao:request_detail', pk=task.pk)
            return redirect('gestao:request_training', pk=task.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'home/gestao/training_case.html', _workspace(request,
        'Regularizar treinamento', person=person, form=form))


class CompletedTrainingForm(forms.Form):
    token = forms.ChoiceField(label='Treinamento já concluído')
    reason = forms.CharField(label='Motivo da regularização', min_length=5, max_length=500,
                             widget=forms.Textarea(attrs={'rows': 2}))
    evidence = forms.CharField(label='Evidência ou referência do registro', min_length=5, max_length=2000,
                               widget=forms.Textarea(attrs={'rows': 3}))
    finish = forms.BooleanField(label='Concluir esta solicitação após registrar o treinamento', required=False)

    def __init__(self, *args, person, **kwargs):
        super().__init__(*args, **kwargs)
        from home.models import TbIdioma, TbItemMundano
        self.fields['token'].choices = [('', 'Selecione'),
            ('Idiomas', [('idioma:' + row.slug, row.nome) for row in TbIdioma.objects.order_by('nome')]),
            ('Ferramentas', [('ferramenta:' + row.slug, row.nome)
              for row in TbItemMundano.objects.filter(categoria='ferramenta').order_by('nome')])]


@never_cache
@require_capability('characters.training')
@require_http_methods(['GET', 'POST'])
def register(request, pk):
    task = get_object_or_404(PortalRequest.objects.select_related('character__dono'), pk=pk)
    if not can_review(request.user, 'ficha') or task.queue != 'ficha' or not task.character_id:
        raise PermissionDenied
    if request.method != 'POST' or request.POST.get('action') != 'confirm':
        _require(request.user, task)
    form = CompletedTrainingForm(person=task.character)
    confirmation = GrantConfirmationForm()
    preview = None
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'confirm':
                confirmation = GrantConfirmationForm(request.POST)
                if confirmation.is_valid():
                    receipt = apply_training(actor=request.user, task_id=task.pk,
                                             ticket=confirmation.cleaned_data['ticket'])
                    messages.success(request, 'Treinamento registrado sem cobrança.' if receipt.after['created']
                                     else 'O personagem já possuía esta proficiência. Nenhuma cobrança realizada.')
                    return redirect('gestao:request_detail', pk=task.pk)
            elif request.POST.get('action') == 'preview':
                form = CompletedTrainingForm(request.POST, person=task.character)
                if form.is_valid():
                    preview = preview_training(actor=request.user, task_id=task.pk, **form.cleaned_data)
                    confirmation = GrantConfirmationForm(initial={'ticket': preview['ticket']})
            else:
                form.add_error(None, 'Ação inválida.')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'home/gestao/training.html', _workspace(request,
        'Registrar treinamento comprovado', management_section='requests', task=task,
        form=form, confirmation_form=confirmation, preview=preview))
