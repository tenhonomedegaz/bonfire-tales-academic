"""Read-only cosmetic discovery. Public art is never an entitlement or an offer."""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .cosmetics import get_catalog, sanitize_definicao_tema


KINDS = {'tema': 'Temas', 'moldura': 'Molduras', 'efeito': 'Efeitos',
         'titulo': 'Títulos', 'badge': 'Insígnias', 'banner_preset': 'Banners'}
STATES = {'disponivel': 'Disponível para usar', 'possuido': 'Na sua biblioteca',
          'obtivel': 'Obtenível', 'futuro': 'Futuro', 'exclusivo': 'Exclusivo',
          'indisponivel': 'Indisponível', 'suspenso': 'Suspenso', 'preparacao': 'Em preparação'}
LEGACY_FRAME_SLUGS = ('moldura-gold-trim', 'moldura-frost', 'moldura-verdant')
EDITORIAL_PATH = Path(__file__).parent / 'static/cosmetics/discovery-editorial.json'


def editorial_proposals():
    """Only this reviewed public manifest is read, never internal drafts or globs."""
    data = json.loads(EDITORIAL_PATH.read_text(encoding='utf-8'))
    if data.get('version') != 1 or data.get('purpose') != 'approved-public-art-proposals-only':
        raise ValueError('Invalid public discovery manifest')
    collections = data['collections']
    entries = data['proposals']
    slugs = set()
    for entry in entries:
        slug = entry['slug']
        if (slug in slugs or entry['tipo'] not in KINDS or
                not slug.startswith(entry['tipo'] + '-') or
                entry['collection'] not in collections or
                entry['escopo'] not in {'perfil', 'ficha', 'ambos'} or
                set(entry) - {'slug', 'collection', 'tipo', 'nome', 'escopo', 'class', 'definition'}):
            raise ValueError('Invalid public proposal')
        slugs.add(slug)
    return entries, collections


def _read_snapshot(user):
    """Catalog cache is public; ownership is batched and scoped to this account only.

    Do not use catalog_options/cosmetic_allowed: those can repair rank grants.
    """
    from .cosmetic_entitlements import permanent_cosmetic_slugs
    from .models import (CosmeticCheckoutOffer, EventCosmeticOffer, TbConquista,
                         TbCosmetico, TbUsuarioCosmetico)
    from .permissions import colab_tier

    catalog = {}
    for kind in KINDS:
        for key, metadata in get_catalog(kind).items():
            catalog[metadata['slug']] = dict(metadata, key=key, tipo=kind)
    slugs = set(catalog)
    inventory = {row['cosmetico__slug']: row for row in
                 TbUsuarioCosmetico.objects.filter(user=user, cosmetico__slug__in=slugs)
                 .values('cosmetico__slug', 'origem', 'suspenso_em')}
    rules = defaultdict(list)
    for rule in TbConquista.objects.filter(ativo=True, secreta=False).values(
            'slug', 'nome', 'descricao', 'criterio', 'recompensa__slug', 'recompensas_extras__slug'):
        for slug in {rule['recompensa__slug'], rule['recompensas_extras__slug']} & slugs:
            if not any(old['slug'] == rule['slug'] for old in rules[slug]):
                rules[slug].append(rule)
    legacy = dict(TbCosmetico.objects.filter(slug__in=LEGACY_FRAME_SLUGS)
                  .values_list('slug', 'ativo'))
    return {
        'catalog': catalog, 'inventory': inventory, 'rules': rules,
        'permanent': permanent_cosmetic_slugs(user),
        'cash': list(CosmeticCheckoutOffer.objects.filter(cosmetico__slug__in=slugs).values(
            'cosmetico__slug', 'active', 'demonstration', 'amount')),
        'events': list(EventCosmeticOffer.objects.filter(cosmetico__slug__in=slugs).values(
            'pk', 'cosmetico__slug', 'active', 'starts_at', 'ends_at', 'cost_braseiros')),
        'tier': colab_tier(user) if any(item['origem'] == 'colaborador'
                                      for item in catalog.values()) else None,
        'legacy': [{'slug': slug, 'status': ('Publicado' if legacy[slug] else 'Inativo')
                    if slug in legacy else 'Ausente no banco'} for slug in LEGACY_FRAME_SLUGS],
    }


def _activation_links(item):
    links = []
    if item['escopo'] in {'perfil', 'ambos'}:
        anchor = '#perfil-insignias' if item['tipo'] in {'badge', 'titulo'} else '#perfil-aparencia'
        links.append({'label': 'Escolher no perfil', 'url': reverse('profile') + anchor})
    if item['escopo'] in {'ficha', 'ambos'} and item['tipo'] in {'tema', 'moldura', 'efeito'}:
        links.append({'label': 'Escolher ficha', 'url': reverse('personagens')})
    return links


def _availability(item, snapshot, now):
    from .cosmetics import _colab_allows
    from .theme_studio import COLLECTIONS, PILOT_CASH_DISABLED_SLUGS

    slug = item['slug']
    origin = item['origem']
    inventory = snapshot['inventory'].get(slug)
    permanent = slug in snapshot['permanent']
    if origin == 'livre':
        return 'disponivel', 'Disponível para sua conta nos escopos publicados.', _activation_links(item)
    if (permanent or (inventory and inventory['suspenso_em'] is None and
                      not inventory['origem'].startswith('colaborador')) or
            (origin == 'colaborador' and _colab_allows(item, snapshot['tier']))):
        return 'possuido', 'Acesso registrado para esta conta.', _activation_links(item)
    if inventory and inventory['suspenso_em'] is not None:
        return 'suspenso', 'Acesso suspenso ou revogado nesta conta, sem outro direito vigente.', []

    cash = next((offer for offer in snapshot['cash'] if offer['cosmetico__slug'] == slug), None)
    if cash and cash['active'] and not cash['demonstration']:
        if (item['tipo'] == 'tema' and origin == 'loja_mm' and item['key'] in COLLECTIONS and
                type(item.get('preco')) is int and item['preco'] > 0 and
                getattr(settings, 'BONFIRE_COMMERCE_ENABLED', False)):
            return 'obtivel', 'Resgate em MM publicado no ateliê.', [{
                'label': 'Ver resgate em MM', 'url': reverse('theme_studio') + '?' + urlencode({'tema': item['key']})}]
        if (cash['amount'] > 0 and not (item['tipo'] == 'tema' and origin == 'loja_mm') and
                not (slug in PILOT_CASH_DISABLED_SLUGS and item.get('class') == 'theme-data')):
            return 'obtivel', 'Oferta de compra publicada.', [{
                'label': 'Ver oferta', 'url': reverse('cosmetic_checkout') + '#cosmetic-offer-' + slug}]

    events = [offer for offer in snapshot['events'] if offer['cosmetico__slug'] == slug
              and origin in {'loja_braseiro', 'evento_manual'}]
    for offer in events:
        if (offer['active'] and (not offer['starts_at'] or offer['starts_at'] <= now) and
                (not offer['ends_at'] or now < offer['ends_at'])):
            return 'obtivel', 'Oferta de evento vigente; confira as condições do resgate.', [{
                'label': 'Ver resgate', 'url': reverse('event_cosmetic_shop') + '#event-offer-' + str(offer['pk'])}]

    rules = snapshot['rules'].get(slug, [])
    if rules:
        rule = next((rule for rule in rules if rule['criterio'] == 'automatico'), rules[0])
        state = 'obtivel' if rule['criterio'] == 'automatico' else 'exclusivo'
        return state, 'Conquista: ' + rule['nome'] + ('. ' + rule['descricao'] if rule['descricao'] else ''), [{
            'label': 'Ver conquistas', 'url': reverse('profile') + '#conquistas'}]
    future = [offer for offer in events if offer['active'] and offer['starts_at'] and now < offer['starts_at']]
    if future:
        start = min(offer['starts_at'] for offer in future)
        return 'futuro', 'Evento previsto para ' + timezone.localtime(start).strftime('%d/%m/%Y %H:%M') + '.', []
    if origin == 'colaborador':
        return 'exclusivo', 'Acesso condicionado ao plano publicado: ' + (item.get('requer_plano') or 'não informado') + '.', [{
            'label': 'Ver colaboração', 'url': reverse('colaborador')}]
    if origin in {'staff', 'mestre_ouro'}:
        return 'exclusivo', 'Concessão exclusiva; não há obtenção pública publicada.', []
    if any(offer['ends_at'] and offer['ends_at'] <= now for offer in events):
        return 'indisponivel', 'Período de evento encerrado; nenhuma obtenção vigente publicada.', []
    return 'indisponivel', 'Nenhuma obtenção vigente publicada.', []


def _preview(item):
    from .cosmetic_packages import load_package
    from .editorial_links import safe_editorial_image

    definition = sanitize_definicao_tema(item.get('definicao'))
    asset = item.get('asset_url') or ''
    image = safe_editorial_image(asset)
    glyph = (asset if item['tipo'] == 'badge' and not image and len(asset) <= 24
             and asset.isprintable() and not any(char in asset for char in '/:\\') else '')
    return {
        'package': load_package(item['tipo'], item['key'], 'ficha' if item['escopo'] == 'ficha' else 'perfil'),
        'image': image, 'glyph': glyph,
        'style': ';'.join('--discovery-' + key + ':' + definition[key]
                          for key in ('accent', 'accent2', 'surface', 'deep') if key in definition),
    }


def build_discovery(snapshot, *, now=None):
    """Pure availability projection over a read-only snapshot; no grants or writes."""
    now = now or timezone.now()
    proposals, collections = editorial_proposals()
    editorial = {entry['slug']: entry for entry in proposals}
    cards = []
    for slug, item in snapshot['catalog'].items():
        collection = editorial.get(slug, {}).get('collection')
        if not collection:
            collection = 'ranks' if item.get('desbloqueio') else 'classicos' if slug in LEGACY_FRAME_SLUGS else 'catalogo'
        state, reason, links = _availability(item, snapshot, now)
        cards.append(dict(item, collection=collection, state=state, reason=reason, links=links,
                          proposal=False, preview=_preview(item)))
    for entry in proposals:
        if entry['slug'] in snapshot['catalog']:
            continue
        item = dict(entry, key=entry['slug'][len(entry['tipo']) + 1:], label=entry['nome'],
                    definicao=entry.get('definition'), descricao='', asset_url='')
        cards.append(dict(item, state='preparacao', reason='Em preparação – obtenção ainda não publicada',
                          links=[], proposal=True, preview=_preview(item)))
    collections = dict(collections, ranks='Ranks', classicos='Clássicos', catalogo='Catálogo')
    for card in cards:
        card['collection_label'] = collections[card['collection']]
        card['state_label'] = STATES[card['state']]
        card['kind_label'] = KINDS[card['tipo']]
        card['scope_label'] = {'perfil': 'Perfil', 'ficha': 'Ficha', 'ambos': 'Perfil e ficha'}[card['escopo']]
    return {'cards': cards, 'collections': collections, 'kinds': KINDS, 'states': STATES,
            'legacy_report': snapshot['legacy']}


def discovery_catalog(user):
    from .cosmetics import cosmetic_read_context
    with cosmetic_read_context():
        return build_discovery(_read_snapshot(user))


def _search_text(value):
    return ''.join(char for char in unicodedata.normalize('NFD', value).casefold()
                   if not unicodedata.combining(char))


def discovery_context(user, parameters):
    context = discovery_catalog(user)
    selected = {'q': (parameters.get('q') or '')[:120].strip()}
    for key, choices in (('tipo', KINDS), ('colecao', context['collections']), ('estado', STATES)):
        value = parameters.get(key, '')
        selected[key] = value if value in choices else ''
    visible = 0
    for card in context['cards']:
        card['search_text'] = ' '.join((card['label'], card['slug'], card['collection_label']))
        card['visible'] = (
            _search_text(selected['q']) in _search_text(card['search_text']) and
            (not selected['tipo'] or selected['tipo'] == card['tipo']) and
            (not selected['colecao'] or selected['colecao'] == card['collection']) and
            (not selected['estado'] or selected['estado'] == card['state']))
        visible += card['visible']
    context.update(selected=selected, visible_count=visible,
                   published_count=sum(not card['proposal'] for card in context['cards']),
                   proposal_count=sum(card['proposal'] for card in context['cards']),
                   page_title='Descobrir cosméticos', ads_enabled=False)
    return context


def discovery_response(request):
    """Avoid the shared get_or_create profile processor on this read-only GET."""
    from django.contrib.auth.context_processors import auth
    from django.http import HttpResponse
    from django.template.context_processors import csrf
    from django.template.loader import render_to_string
    from .context_processors import master_review, site_presentation
    from .models import UserProfile

    context = discovery_context(request.user, request.GET)
    context.update(site_presentation(request), **auth(request))
    context.update(master_review(request))
    context.update(csrf(request))
    context.update(request=request, user=request.user,
                   user_profile=UserProfile.objects.filter(user=request.user).first(), noindex=True)
    response = HttpResponse(render_to_string('home/pages/cosmetic_discovery.html', context))
    response['Cache-Control'] = 'private, no-store'
    from django.utils.cache import patch_vary_headers
    patch_vary_headers(response, ('Cookie',))
    return response
