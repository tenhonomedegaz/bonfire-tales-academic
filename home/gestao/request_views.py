from uuid import uuid4
from urllib.parse import urlencode
import re

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from home.models import TbPersonagem
from home.portal_models import PortalActivity
from .requests import act_on_request, create_request, visible_requests
from .workflows import ACTION_LABELS, QUEUES, STATUSES, allowed_actions, can_review


class RequestForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    queue = forms.ChoiceField(label='Área responsável', choices=[(key, value[0]) for key, value in QUEUES.items()])
    title = forms.CharField(label='Título', min_length=3, max_length=200)
    character = forms.ModelChoiceField(label='Personagem', queryset=TbPersonagem.objects.none(), required=False)
    description = forms.CharField(label='Descrição', min_length=5, max_length=8000,
                                  widget=forms.Textarea(attrs={'rows': 7}))
    reference_url = forms.URLField(label='Link de referência', max_length=2000, required=False)

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['character'].queryset = TbPersonagem.objects.filter(dono=actor).order_by('nome', 'pk')


class ActionForm(forms.Form):
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    action = forms.ChoiceField(label='Encaminhamento')
    note = forms.CharField(label='Comentário ou parecer', min_length=3, max_length=8000,
                           widget=forms.Textarea(attrs={'rows': 4}))
    description = forms.CharField(label='Descrição revisada', min_length=5, max_length=8000,
                                  required=False, widget=forms.Textarea(attrs={'rows': 6}))

    def __init__(self, *args, actions, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = [(key, ACTION_LABELS[key]) for key in actions]
        if 'resubmit' not in actions:
            self.fields.pop('description')


def portal_context(user):
    visible = visible_requests(user)
    counts = {row['queue']: row for row in visible.values('queue').annotate(
        total=Count('pk'), pending=Count('pk', filter=Q(status__in=['new', 'reviewing', 'waiting'])))}
    queues = [{'key': key, 'label': value[0],
               'url': reverse('gestao:requests') + '?' + urlencode({'queue': key}),
               'total': counts.get(key, {}).get('total', 0),
               'pending': counts.get(key, {}).get('pending', 0),
               'can_review': can_review(user, key)} for key, value in QUEUES.items()
              if can_review(user, key) or key in counts]
    return {'portal_queues': queues, 'portal_total_pending': sum(row['pending'] for row in queues),
            'portal_requests_url': reverse('gestao:requests'),
            'portal_create_url': reverse('gestao:request_create'),
            'portal_recent_activity': PortalActivity.objects.filter(task__in=visible)
                .select_related('actor', 'task').order_by('-created_at', '-pk')[:8]}


def _context(request, title, **kwargs):
    from .views import _workspace
    return _workspace(request, title, management_section='requests', **kwargs)


def _active(request):
    if not request.user.is_active:
        raise PermissionDenied


@never_cache
@login_required(login_url='login')
@require_GET
def index(request):
    _active(request)
    tasks = visible_requests(request.user).select_related('requester', 'assignee', 'character')
    queue = request.GET.get('queue', '')
    status = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()[:150]
    if queue in QUEUES:
        tasks = tasks.filter(queue=queue)
    else:
        queue = ''
    if status in dict(STATUSES):
        tasks = tasks.filter(status=status)
    else:
        status = ''
    if query:
        reference = re.fullmatch(r'(st|lo|de|ru|me)-(\d{1,18})', query, flags=re.IGNORECASE)
        if reference:
            tasks = tasks.filter(pk=int(reference[2]), queue__in=[
                key for key, value in QUEUES.items() if value[2] == reference[1].lower()])
        else:
            tasks = tasks.filter(Q(title__icontains=query) | Q(character__nome__icontains=query)
                                 | Q(requester__username__icontains=query))
    page = Paginator(tasks, 25).get_page(request.GET.get('page'))
    filters = {'queue': queue, 'status': status, 'q': query}
    return render(request, 'home/gestao/requests.html', _context(request, 'Atendimento',
        tasks=page, queue_choices=list(QUEUES.items()), status_choices=STATUSES,
        filters=filters, pagination_query=urlencode(filters)))


@never_cache
@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def create(request):
    _active(request)
    form = RequestForm(request.POST or None, actor=request.user,
                       initial={'request_id': uuid4(), 'queue': request.GET.get('queue', 'ticket')})
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        try:
            task = create_request(actor=request.user, request_id=data['request_id'],
                queue=data['queue'], title=data['title'], description=data['description'],
                reference_url=data['reference_url'], character_id=data['character'].pk if data['character'] else None)
            return redirect('gestao:request_detail', pk=task.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'home/gestao/request_create.html', _context(request, 'Nova solicitação', form=form))


@never_cache
@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def detail(request, pk):
    _active(request)
    task = get_object_or_404(visible_requests(request.user).select_related('requester', 'assignee', 'character'), pk=pk)
    actions = allowed_actions(request.user, task)
    from .training import can_register_training
    from .character_profile import can_correct_profile, PROFILE_FIELDS
    from .policy import can
    form = ActionForm(request.POST or None, actions=actions,
        initial={'request_id': uuid4(), 'version': task.version, 'description': task.description})
    if request.method == 'POST' and form.is_valid():
        try:
            act_on_request(actor=request.user, task_id=task.pk, **form.cleaned_data)
            messages.success(request, 'Encaminhamento registrado.')
            return redirect('gestao:request_detail', pk=task.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    history = Paginator(task.activities.select_related('actor').order_by('-created_at', '-pk'), 25).get_page(
        request.GET.get('history_page'))
    events = [{'event': event, 'label': ACTION_LABELS.get(event.action, event.action)}
              for event in history]
    if task.character_id and (task.character.dono_id == request.user.pk or
            (can(request.user, 'characters.profile') and can_review(request.user, 'ficha'))):
        for row in events:
            event = row['event']
            if event.action == 'profile':
                before, after = event.before.get('fields', {}), event.after.get('fields', {})
                row['changes'] = [{'label': PROFILE_FIELDS[key], 'before': before.get(key) or '',
                                  'after': value or ''} for key, value in after.items() if key in PROFILE_FIELDS]
    return render(request, 'home/gestao/request_detail.html', _context(request, task.reference,
        task=task, events=events, history=history, form=form, actions=actions,
        can_register_training=can_register_training(request.user, task),
        can_correct_profile=can_correct_profile(request.user, task)))
