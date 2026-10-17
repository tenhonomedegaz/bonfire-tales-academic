"""Pilot theme gallery backed by the existing cosmetic catalog."""

import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .cosmetics import cosmetic_allowed
from .models import CosmeticCheckoutOffer
from .theme_mm import redeem_theme_mm


# Presentation from the pinned redesign. Catalog rows remain the source of
# availability, price and ownership; this metadata does not grant anything.
COLLECTIONS = {
    'forja-de-brasas': ('brasas', 'Uma chama que acompanha a sua história.', 'fogo'),
    'aurora-glacial': ('glacial', 'O silêncio antes da próxima descoberta.', 'gelo'),
    'circulo-arcano': ('arcano', 'Toda magia deixa uma assinatura.', 'arcano'),
}
PILOT_CASH_DISABLED_SLUGS = frozenset('tema-' + key for key in COLLECTIONS)


@require_GET
def theme_studio(request):
    offers = {offer.cosmetico.slug: offer for offer in
              CosmeticCheckoutOffer.objects.select_related('cosmetico').filter(
                  active=True, cosmetico__ativo=True, cosmetico__tipo='tema')}
    cards = []
    for key, (sample, subtitle, affinity) in COLLECTIONS.items():
        offer = offers.get('tema-' + key)
        if offer is None:
            continue
        item = offer.cosmetico
        cards.append({
            'key': key, 'sample': sample, 'subtitle': subtitle, 'affinity': affinity,
            'name': item.nome, 'description': item.descricao,
            'price_brl': offer.amount, 'price_mm': item.preco if item.origem == 'loja_mm' else None,
            'mm_only': item.origem == 'loja_mm',
            'cash_disabled': (item.slug in PILOT_CASH_DISABLED_SLUGS
                              and item.css_class == 'theme-data' and item.origem != 'loja_mm'),
            'demonstration': offer.demonstration, 'offer': offer,
            'owned': cosmetic_allowed(request.user, 'tema', key, 'ficha'),
            'request_key': uuid.uuid4(),
        })
    selected = next((card for card in cards if card['key'] == request.GET.get('tema')),
                    cards[0] if cards else None)
    return render(request, 'home/pages/theme_studio.html', {
        'page_title': 'Ateliê de identidades', 'ads_enabled': False,
        'cards': cards, 'selected': selected,
        'studio_demo': any(card['demonstration'] or card['cash_disabled'] for card in cards),
        'commerce_enabled': bool(getattr(settings, 'BONFIRE_COMMERCE_ENABLED', False)),
    })


@login_required
@require_POST
def buy_theme_with_mm(request):
    if not getattr(settings, 'BONFIRE_COMMERCE_ENABLED', False):
        return render(request, 'home/pages/theme_acquisition.html', {
            'page_title': 'Resgate indisponível', 'error': 'Resgate em MM indisponível.',
        }, status=403)
    try:
        request_key = uuid.UUID(request.POST.get('request_key', ''))
    except (ValueError, TypeError, AttributeError):
        request_key = None
    slug = request.POST.get('slug', '')
    if not request_key or not slug:
        return render(request, 'home/pages/theme_acquisition.html', {
            'page_title': 'Resgate inválido', 'error': 'Solicitação de resgate inválida.',
        }, status=400)
    try:
        receipt, created = redeem_theme_mm(request.user.pk, slug, request_key)
    except ValueError as exc:
        return render(request, 'home/pages/theme_acquisition.html', {
            'page_title': 'Resgate não concluído', 'error': str(exc),
        }, status=400)
    return render(request, 'home/pages/theme_acquisition.html', {
        'page_title': 'Tema na biblioteca', 'receipt': receipt,
        'created': created,
    })
