from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import CharField, Exists, OuterRef, Q, Subquery, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from home.cosmetic_picker import _presentation_metadata, _thumbnail_url
from home.gestao_models import ManualCosmeticGrantReceipt
from home.models import (CosmeticCheckoutPurchase, CosmeticMMRedemption,
                         EventCosmeticRedemption, TbCosmetico, TbUsuarioCosmetico)

from .forms import (CosmeticCatalogFilterForm, GrantConfirmationForm,
                    ManualGrantForm, PeopleSearchForm)
from .policy import can, require_capability
from .services import apply_manual_grant, preview_manual_grant


def _workspace(request, title, **context):
    people_access = can(request.user, 'people.view')
    cosmetics_access = people_access and can(request.user, 'cosmetics.view')
    return {
        'page_title': title,
        'noindex': True,
        'ads_enabled': False,
        'can_view_people': people_access,
        'can_view_cosmetics': cosmetics_access,
        'can_grant_cosmetics': cosmetics_access and can(request.user, 'cosmetics.grant_manual'),
        'can_view_email': bool(request.user.is_superuser),
        'management_section': 'people',
        **context,
    }


def _url(name, params=None, **kwargs):
    path = reverse('gestao:' + name, kwargs=kwargs)
    query = urlencode({key: value for key, value in (params or {}).items() if value != ''})
    return path + ('?' + query if query else '')


def _person_navigation(request, target):
    # Only carry known search parameters; never accept a return URL from the client.
    q = request.GET.get('people_q', '')[:150]
    page = request.GET.get('people_page', '1')
    page = page if page.isdigit() and len(page) < 9 else '1'
    params = {'people_q': q, 'people_page': page}
    return {
        'people_url': _url('people', {'q': q, 'page': page}),
        'person_url': _url('person', params, user_id=target.pk),
        'inventory_url': _url('person', {**params, 'tab': 'inventory'}, user_id=target.pk),
        'history_url': _url('person', {**params, 'tab': 'history'}, user_id=target.pk),
        'grant_url': _url('grant', params, user_id=target.pk),
    }


def _page_context(request, queryset, *, per_page=25, anchor='results'):
    page = Paginator(queryset, per_page).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    def page_url(number):
        query = params.copy()
        query['page'] = number
        return '?' + query.urlencode() + '#' + anchor
    return {
        'page_obj': page,
        'previous_url': page_url(page.previous_page_number()) if page.has_previous() else '',
        'next_url': page_url(page.next_page_number()) if page.has_next() else '',
    }


def _receipts(user):
    return ManualCosmeticGrantReceipt.objects.filter(user=user).select_related(
        'actor', 'cosmetico').order_by('-criado_em', '-pk')


def _thumbnail(cosmetic, registry):
    metadata = registry.get(cosmetic.slug, {})
    if not isinstance(metadata, dict):
        metadata = {}
    # The approved thumbnail registry avoids loading animation packages or atlases.
    return _thumbnail_url(
        {'asset_url': '' if cosmetic.animado else cosmetic.asset_efetivo}, metadata)


def _inventory(target):
    inventory = TbUsuarioCosmetico.objects.filter(user=target)
    paid = CosmeticCheckoutPurchase.objects.filter(beneficiary=target, granted_at__isnull=False)
    mm = CosmeticMMRedemption.objects.filter(user=target, reversed_at__isnull=True)
    event = EventCosmeticRedemption.objects.filter(user=target)
    row = inventory.filter(cosmetico_id=OuterRef('pk'))
    return TbCosmetico.objects.filter(
        Q(pk__in=inventory.values('cosmetico_id')) |
        Q(pk__in=paid.values('cosmetico_id')) |
        Q(pk__in=mm.values('cosmetico_id')) |
        Q(pk__in=event.values('cosmetico_id')),
    ).annotate(
        inventory_exists=Exists(row),
        inventory_origin=Subquery(row.values('origem')[:1]),
        inventory_suspended_at=Subquery(row.values('suspenso_em')[:1]),
        inventory_granted_at=Subquery(row.values('desbloqueado_em')[:1]),
        paid_source=Exists(paid.filter(cosmetico_id=OuterRef('pk'))),
        mm_source=Exists(mm.filter(cosmetico_id=OuterRef('pk'))),
        event_source=Exists(event.filter(cosmetico_id=OuterRef('pk'))),
        manual_source=Exists(_receipts(target).filter(
            cosmetico_id=OuterRef('pk'), outcome='granted')),
    ).order_by('nome', 'pk')


def _inventory_item(cosmetic, registry):
    sources = []
    for exists, label in (
        (cosmetic.paid_source, 'Compra confirmada'),
        (cosmetic.mm_source, 'Resgate com MM'),
        (cosmetic.event_source, 'Resgate de evento'),
        (cosmetic.manual_source, 'Concessão manual com recibo'),
    ):
        if exists:
            sources.append(label)
    origin = cosmetic.inventory_origin or ''
    origin_labels = {
        'staff': 'Concessão da equipe', 'seed': 'Inventário inicial',
        'compra_mm': 'Compra com MM', 'compra_asaas': 'Compra',
        'evento_manual': 'Evento manual',
    }
    if cosmetic.inventory_exists:
        if origin.startswith('conquista:'):
            source = 'Conquista: ' + origin.partition(':')[2]
        elif origin.startswith('rank:'):
            source = 'Recompensa de rank: ' + origin.partition(':')[2]
        else:
            source = origin_labels.get(origin, origin or 'Origem não informada')
        if source not in sources:
            sources.append(source)
    permanent = cosmetic.paid_source or cosmetic.mm_source or cosmetic.event_source
    if not cosmetic.ativo:
        status, tone = 'Item inativo', 'muted'
    elif permanent:
        status, tone = 'Direito permanente', 'success'
    elif cosmetic.origem == 'livre':
        status, tone = 'Disponível para todos', 'success'
    elif cosmetic.inventory_suspended_at:
        status, tone = 'Concessão suspensa', 'warning'
    else:
        status, tone = 'Disponível', 'success'
    return {
        'cosmetic': cosmetic, 'thumbnail_url': _thumbnail(cosmetic, registry),
        'sources': sources, 'status': status, 'tone': tone,
        'inventory_suspended_at': cosmetic.inventory_suspended_at,
        'granted_at': cosmetic.inventory_granted_at,
    }


@never_cache
@require_GET
def index(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    if not (can(request.user, 'people.view') or can(request.user, 'character_history.review')):
        raise PermissionDenied
    context = _workspace(request, 'Gestão', management_section='index',
                         can_review_history=can(request.user, 'character_history.review'),
                         search_form=PeopleSearchForm(), recent_receipts=[])
    if context['can_view_cosmetics']:
        context['recent_receipts'] = ManualCosmeticGrantReceipt.objects.filter(
            actor=request.user).select_related('user', 'cosmetico').order_by('-criado_em', '-pk')[:8]
    return render(request, 'home/gestao/index.html', context)


@never_cache
@require_capability('people.view')
@require_GET
def people(request):
    form = PeopleSearchForm(request.GET)
    users = get_user_model().objects.select_related('profile').prefetch_related('groups')
    if form.is_valid():
        query = form.cleaned_data['q']
        if query:
            users = users.annotate(management_full_name=Concat(
                'first_name', Value(' '), 'last_name', output_field=CharField()))
            lookup = (Q(username__icontains=query) | Q(management_full_name__icontains=query) |
                      Q(profile__discord_username__icontains=query) |
                      Q(profile__discord_user_id__icontains=query))
            if request.user.is_superuser:
                lookup |= Q(email__icontains=query)
            users = users.filter(lookup)
    else:
        query = ''
        users = users.none()
    pagination = _page_context(request, users.order_by('username', 'pk'))
    rows = [{
        'person': user,
        'url': _url('person', {'people_q': query, 'people_page': pagination['page_obj'].number},
                    user_id=user.pk),
    } for user in pagination['page_obj']]
    return render(request, 'home/gestao/people.html', _workspace(
        request, 'Pessoas', search_form=form, people_rows=rows, **pagination))


@never_cache
@require_capability('people.view')
@require_GET
def person(request, user_id):
    target = get_object_or_404(get_user_model().objects.select_related('profile').prefetch_related('groups'),
                               pk=user_id)
    tab = request.GET.get('tab', 'overview')
    if tab not in {'overview', 'inventory', 'history'}:
        tab = 'overview'
    if tab != 'overview' and not can(request.user, 'cosmetics.view'):
        raise PermissionDenied
    context = _workspace(request, target.get_full_name() or target.username,
                         target=target, active_tab=tab, **_person_navigation(request, target))
    if context['can_view_cosmetics']:
        context['inventory_count'] = _inventory(target).count()
        context['receipt_count'] = _receipts(target).count()
    if tab == 'inventory':
        context.update(_page_context(request, _inventory(target)))
        registry = _presentation_metadata()
        context['inventory_rows'] = [_inventory_item(item, registry) for item in context['page_obj']]
    elif tab == 'history':
        context.update(_page_context(request, _receipts(target)))
    return render(request, 'home/gestao/person.html', context)


@never_cache
@require_capability('people.view')
@require_capability('cosmetics.view')
@require_capability('cosmetics.grant_manual')
@require_http_methods(['GET', 'POST'])
def grant(request, user_id):
    target = get_object_or_404(get_user_model().objects.select_related('profile'), pk=user_id)
    action = request.POST.get('action') if request.method == 'POST' else None
    if action in {'edit', 'browse'}:
        form = ManualGrantForm(initial={key: request.POST.get(key, '')
                                        for key in ('cosmetic_id', 'reason')})
    else:
        form = ManualGrantForm(request.POST if request.method == 'POST' else None)
    filters = CosmeticCatalogFilterForm(request.GET)
    preview = None
    confirmation = GrantConfirmationForm()
    if request.method == 'POST':
        try:
            if action == 'preview' and form.is_valid():
                preview = preview_manual_grant(
                    actor=request.user, user_id=target.pk,
                    cosmetic_id=form.cleaned_data['cosmetic_id'], reason=form.cleaned_data['reason'])
                confirmation = GrantConfirmationForm(initial={'ticket': preview['ticket']})
            elif action == 'confirm':
                confirmation = GrantConfirmationForm(request.POST)
                if confirmation.is_valid():
                    receipt = apply_manual_grant(actor=request.user,
                                                 ticket=confirmation.cleaned_data['ticket'],
                                                 expected_user_id=target.pk)
                    if receipt.outcome == 'already_owned':
                        messages.info(request, f'{receipt.user.username} já possui {receipt.cosmetico.nome}. '
                                              'O direito existente foi preservado e a ação foi registrada.')
                    else:
                        messages.success(request, f'{receipt.cosmetico.nome} concedido a '
                                                 f'{receipt.user.username}. Recibo registrado.')
                    return redirect(_person_navigation(request, receipt.user)['history_url'])
                for error in confirmation.errors.get('ticket', []):
                    form.add_error(None, error)
            elif action not in {'preview', 'edit', 'browse'}:
                form.add_error(None, 'Ação inválida. Confira uma nova prévia antes de confirmar.')
        except ValidationError as error:
            for message in error.messages:
                form.add_error(None, message)

    catalog = TbCosmetico.objects.all()
    if filters.is_valid():
        query, kind = filters.cleaned_data['q'], filters.cleaned_data['type']
        if query:
            catalog = catalog.filter(Q(nome__icontains=query) | Q(descricao__icontains=query))
        if kind:
            catalog = catalog.filter(tipo=kind)
    else:
        catalog = catalog.none()
    pagination = _page_context(request, catalog.order_by('-ativo', 'tipo', 'nome', 'pk'), per_page=24)
    registry = _presentation_metadata()
    selected_id = str(form['cosmetic_id'].value() or '')
    catalog_rows = [{
        'cosmetic': item, 'thumbnail_url': _thumbnail(item, registry),
        'selected': str(item.pk) == selected_id,
    } for item in pagination['page_obj']]
    selected = TbCosmetico.objects.filter(pk=int(selected_id)).first() if (
        selected_id.isdecimal() and len(selected_id) < 19) else None
    return render(request, 'home/gestao/grant.html', _workspace(
        request, 'Conceder cosmético', target=target, form=form, filter_form=filters,
        preview=preview, confirmation_form=confirmation, catalog_rows=catalog_rows,
        selected_on_page=any(row['selected'] for row in catalog_rows),
        selected_cosmetic=selected, selected_thumbnail=_thumbnail(selected, registry) if selected else '',
        **pagination, **_person_navigation(request, target)))
