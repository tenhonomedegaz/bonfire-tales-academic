"""Private staff UI. All reconciliation writes belong to character_log_review."""
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods

from . import character_log_review as service
from .gestao.policy import can, require_capability


STATES = (
    ('staff_record', 'Log da staff aprovado'),
    ('pending', 'Pendente'), ('matched', 'Vinculado'), ('reviewed', 'Revisado'),
    ('rejected', 'Rejeitado'), ('stale', 'Origem alterada'), ('all', 'Todos'),
)
CATEGORIES = (
    ('mission', 'Missao'), ('staff_bonus', 'Bonificacao de equipe'),
    ('server_boost', 'Impulso do servidor'), ('mm_redemption', 'Resgate MM'),
    ('event_exchange', 'Troca de evento'), ('adjustment', 'Ajuste'),
)
ACTIONS = (
    ('link_mission', 'Vincular missao selecionada'),
    ('link_redemption', 'Vincular recibo MM selecionado'),
    ('verify_bonus', 'Validar bonificacao'),
    ('register_missing_mission', 'Registrar missao legada ausente'),
    ('reject', 'Rejeitar registro'), ('reopen', 'Reabrir revisao'),
)


class QueueForm(forms.Form):
    state = forms.ChoiceField(choices=STATES, required=False, initial='pending')
    q = forms.CharField(max_length=150, required=False)
    source_id = forms.IntegerField(min_value=1, max_value=9223372036854775807, required=False)


class CatalogForm(forms.Form):
    catalog = forms.ChoiceField(label='Catalogo', choices=(('missions', 'Missoes'), ('redemptions', 'Recibos MM')))
    query = forms.CharField(label='Nome da missao ou descricao do recibo', max_length=150, required=False,
                           widget=forms.TextInput(attrs={'type': 'search'}))

    def clean(self):
        data = super().clean()
        if data.get('catalog') == 'missions' and len(data.get('query', '')) < 2:
            self.add_error('query', 'Informe pelo menos 2 caracteres para buscar missoes.')
        return data


class ReviewForm(forms.Form):
    def __init__(self, action, *args, allow_financial=False, **kwargs):
        super().__init__(*args, auto_id=action + '_%s', **kwargs)
        self.action = action
        if action in ('link_mission', 'link_redemption'):
            self.fields['reference'] = forms.CharField(label='Referencia', max_length=160,
                                                       widget=forms.HiddenInput())
        if action == 'verify_bonus':
            self.fields['reference'] = forms.CharField(
                label='Recibo MM da troca de evento (opcional nas outras categorias)',
                max_length=160, required=False,
                widget=forms.TextInput(attrs={'placeholder': 'mm:ID ou purchase:ID'}))
            self.fields['category'] = forms.ChoiceField(label='Categoria', choices=[
                pair for pair in CATEGORIES if pair[0] not in ('mission', 'mm_redemption')])
        if action == 'register_missing_mission':
            self.fields['title'] = forms.CharField(label='Titulo', min_length=2, max_length=500)
            self.fields['date'] = forms.DateField(label='Data', input_formats=['%Y-%m-%d'],
                widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
            self.fields['master'] = forms.CharField(label='Mestre', min_length=2, max_length=200)
            if allow_financial:
                self.fields['master_number'] = forms.IntegerField(
                    label='Fogueira do mestre (opcional; somente reserva sem conta ativa)', min_value=1, required=False)
                self.fields['master_mm'] = forms.IntegerField(
                    label='MM autorizados para reservar (opcional; nao paga o personagem)',
                    min_value=1, max_value=100000, required=False)
        if action not in ('reject', 'reopen'):
            self.fields['adventures'] = forms.IntegerField(label='Aventuras confirmadas (opcional)',
                min_value=0, max_value=99999, required=False)
        self.fields['note'] = forms.CharField(label='Justificativa', max_length=2000,
            min_length=5, widget=forms.Textarea(attrs={'rows': 2}))
        self.fields['evidence'] = forms.CharField(label='Evidencia', max_length=3000,
            min_length=8, required=action not in ('reject', 'reopen'),
            widget=forms.Textarea(attrs={'rows': 3}))

    def clean(self):
        data = super().clean()
        if self.action == 'verify_bonus' and data.get('category') == 'event_exchange':
            if not data.get('reference'):
                self.add_error('reference', 'Selecione o recibo MM da troca de evento no catalogo.')
            if data.get('adventures') is None or data['adventures'] < 1:
                self.add_error('adventures', 'Troca de evento exige ao menos 1 aventura confirmada.')
        return data


def _url(name='character_log_reviews', params=None, **kwargs):
    path = reverse('gestao:' + name, kwargs=kwargs)
    query = urlencode({k: v for k, v in (params or {}).items() if v not in ('', None)})
    return path + ('?' + query if query else '')


def _render(request, context, status=200):
    response = render(request, 'home/gestao/character_log_reviews.html', {
        'page_title': 'Conciliacao de historico', 'noindex': True, 'ads_enabled': False,
        'management_section': 'character_log_reviews',
        'can_view_people': can(request.user, 'people.view'),
        'can_review_history': can(request.user, 'character_history.review'),
        'root_url': _url(), **context,
    }, status=status)
    response['Referrer-Policy'] = 'same-origin'
    return response


def _entry_row(entry):
    return {'entry': entry, 'state_label': dict(STATES).get(entry.state, 'Desconhecido'),
            'category_label': dict(CATEGORIES).get(entry.category, 'Nao classificado')}


@never_cache
@require_capability('character_history.review')
@require_GET
def index(request):
    service.require_reviewer(request.user)
    params = request.GET.copy()
    params['state'] = params.get('state') or 'pending'
    form = QueueForm(params)
    context = {'filter_form': form, 'states': STATES}
    if not form.is_valid():
        return _render(request, {**context, 'error': 'Filtros invalidos. Confira os campos.'}, 400)
    filters = form.cleaned_data
    filters['state'] = filters['state'] or 'pending'
    try:
        queue = service.review_queue(request.user, **filters).order_by('-updated_at', '-pk')
        page = Paginator(queue, 25).get_page(request.GET.get('page'))
        context.update(filters=filters, page_obj=page, rows=[_entry_row(entry) for entry in page],
            previous_url=_url(params={**filters, 'page': page.previous_page_number()}) if page.has_previous() else '',
            next_url=_url(params={**filters, 'page': page.next_page_number()}) if page.has_next() else '')
    except ValidationError as exc:
        return _render(request, {**context, 'error': '; '.join(exc.messages)[:1000]}, 400)
    except DatabaseError:
        return _render(request, {**context, 'error': 'Fila indisponivel. Tente novamente mais tarde.'}, 503)
    return _render(request, context)


def _entry(actor, entry_id):
    return get_object_or_404(service.review_queue(actor, state='all'), pk=entry_id)


def _detail_context(request, entry, bound_form=None):
    version = service.entry_version(entry)
    forms_list = []
    for action, label in ACTIONS:
        form = bound_form if bound_form is not None and bound_form.action == action else ReviewForm(
            action, allow_financial=request.user.is_superuser)
        forms_list.append({'action': action, 'label': label, 'form': form,
                           'open': form.is_bound, 'catalog': action in ('link_mission', 'link_redemption')})
    audits = Paginator(entry.reviews.select_related('actor').order_by('-created_at', '-pk'), 25).get_page(
        request.GET.get('audit_page'))
    audit_rows = []
    for audit in audits:
        snapshots = []
        for snapshot in (audit.before, audit.after):
            snapshot = snapshot if isinstance(snapshot, dict) else {}
            snapshots.append({'state': dict(STATES).get(snapshot.get('state'), 'Nao informado'),
                              'category': dict(CATEGORIES).get(snapshot.get('category'), 'Nao informada'),
                              'reference': snapshot.get('reference', ''),
                              'adventures': snapshot.get('adventures_confirmed')})
        audit_rows.append({'review': audit, 'before': snapshots[0], 'after': snapshots[1]})
    observed = entry.observed if isinstance(entry.observed, dict) else {}
    rewards = observed.get('declared_rewards', {})
    rewards = rewards if isinstance(rewards, dict) else {}
    declared_rewards = [{'label': label, 'value': rewards[key]} for key, label in (
        ('wealth_gained', 'Riqueza recebida'), ('wealth_spent', 'Riqueza gasta'),
        ('special_spent', 'Missao especial gasta'), ('boost_spent', 'Boost gasto'),
        ('embers_gained', 'Braseiros recebidos'), ('event_coins_spent', 'Moedas de evento gastas'),
    ) if key in rewards]
    return {**_entry_row(entry), 'version': version, 'review_forms': forms_list,
        'can_review_entry': request.user.is_superuser or request.user.pk != entry.source.owner_id,
        'source_guild_id': entry.last_seen_batch.snapshot.get('guild_id', ''),
        'declared_category': dict(CATEGORIES).get(observed.get('category'), 'Nao informada'),
        'declared_rewards': declared_rewards,
        'detail_url': _url('character_log_review_detail', entry_id=entry.pk),
        'catalog_form': CatalogForm(initial={'catalog': 'missions', 'query': str(observed.get('title', ''))[:150]}),
        'catalog_results': service.suggested_missions(request.user, entry), 'catalog_kind': 'missions',
        'audit_rows': audit_rows,
        'audit_page': audits,
        'audit_previous': '?audit_page=' + str(audits.previous_page_number()) + '#audit' if audits.has_previous() else '',
        'audit_next': '?audit_page=' + str(audits.next_page_number()) + '#audit' if audits.has_next() else ''}


@never_cache
@require_capability('character_history.review')
@sensitive_post_parameters('evidence', 'note')
@require_http_methods(['GET', 'POST'])
@csrf_protect
def detail(request, entry_id):
    actor = request.user
    service.require_reviewer(actor)
    entry = _entry(actor, entry_id)
    form = None
    error = ''
    status = 200
    if request.method == 'POST':
        if not actor.is_superuser and actor.pk == entry.source.owner_id:
            raise PermissionDenied
        action = request.POST.get('action', '')
        expected = request.POST.get('expected_version', '')
        if action not in dict(ACTIONS):
            error, status = 'Acao invalida. Nenhuma revisao foi gravada.', 400
        elif not expected or len(expected) != 64:
            error, status = 'Versao ausente ou invalida. Recarregue o registro.', 400
        elif not constant_time_compare(expected, service.entry_version(entry)):
            error, status = 'Este registro mudou. Confira os dados atuais antes de reenviar.', 409
        else:
            form = ReviewForm(action, request.POST, allow_financial=actor.is_superuser)
            if not form.is_valid():
                error, status = 'Confira os campos da revisao. Nenhuma alteracao foi gravada.', 400
            else:
                data = dict(form.cleaned_data)
                if action == 'register_missing_mission':
                    data['date'] = data['date'].isoformat()
                try:
                    service.review_entry(actor, entry.pk, expected, action, **data)
                except ValidationError as exc:
                    entry = _entry(actor, entry_id)
                    codes = {item.code for items in getattr(exc, 'error_dict', {}).values() for item in items}
                    codes.update(item.code for item in getattr(exc, 'error_list', []))
                    if not constant_time_compare(expected, service.entry_version(entry)) or codes.intersection(
                            {'conflict', 'stale', 'version_conflict', 'stale_version'}):
                        error, status = '; '.join(exc.messages)[:1000], 409
                        form = None
                    else:
                        error, status = '; '.join(exc.messages)[:1000], 400
                except DatabaseError:
                    error, status = 'Nao foi possivel confirmar a revisao. Recarregue e confira a auditoria antes de tentar novamente.', 503
                else:
                    messages.success(request, 'Historico e MM reservados a Fogueira; nenhuma conta ou personagem recebeu credito.'
                        if data.get('master_mm') else 'Revisao registrada. Nenhum credito ou recompensa foi concedido.')
                    return redirect(_url('character_log_review_detail', entry_id=entry.pk))
    context = _detail_context(request, entry, form)
    if request.method == 'GET' and 'catalog' in request.GET:
        catalog_form = CatalogForm(request.GET)
        context['catalog_form'] = catalog_form
        context['catalog_searched'] = True
        if catalog_form.is_valid():
            data = catalog_form.cleaned_data
            context['catalog_kind'] = data['catalog']
            try:
                if data['catalog'] == 'missions':
                    if not context['source_guild_id']:
                        raise ValidationError('Servidor da origem ausente.')
                    results = service.search_missions(actor, data['query'],
                        guild_id=context['source_guild_id'], limit=20)
                else:
                    results = service.search_redemptions(actor, entry, data['query'], limit=20)
                context['catalog_results'] = results[:20]
            except ValidationError as exc:
                error, status = '; '.join(exc.messages)[:1000], 400
            except DatabaseError:
                error, status = 'Catalogo indisponivel. Tente novamente mais tarde.', 503
        else:
            error, status = 'Confira os campos da busca.', 400
    return _render(request, {**context, 'error': error}, status)
