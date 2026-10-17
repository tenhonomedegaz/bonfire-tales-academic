"""Seed or close the pinned G01-D pilot only after a verified snapshot."""

import json
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.management.commands.reconcile_redesign_d_rewards import _read_json
from home.management.commands.preview_redesign_d import database_identity
from home.models import (CosmeticCheckoutOffer, CosmeticCheckoutPurchase,
                         CosmeticMMRedemption,
                         EventCosmeticRedemption, TbCosmetico, TbUsuarioCosmetico)


PILOT = {
    'forja-de-brasas': ('Forja de Brasas', 'Geometria incandescente, molduras de metal escuro e um cabeçalho em brasa.',
                       '9.90', 1500, '#ff833b', '#b31515', '#1b120f', '#0d0908'),
    'aurora-glacial': ('Aurora Glacial', 'Facetas de gelo, luz fria e detalhes prateados para jornadas sob o inverno.',
                       '14.90', None, '#9bdde8', '#457cbb', '#101a24', '#090f17'),
    'circulo-arcano': ('Círculo Arcano', 'Círculos concêntricos, linhas rituais e violeta profundo compõem sua assinatura arcana.',
                       '12.90', 2000, '#d7b3f4', '#8652b8', '#1b1425', '#100b17'),
}


def _expected(key, values):
    name, description, amount, mm, accent, accent2, surface, deep = values
    return ({
        'slug': 'tema-' + key, 'tipo': 'tema', 'nome': name, 'descricao': description,
        'escopo': 'ambos', 'origem': 'loja_mm' if mm else 'staff', 'preco': mm,
        'ativo': True, 'raridade': 'raro', 'css_class': 'theme-data',
        'definicao_json': dict(accent=accent, accent2=accent2, surface=surface, deep=deep,
                               gradiente=True, particula='nenhuma', vel='lenta', glow=False),
    }, Decimal(amount))


class Command(BaseCommand):
    help = 'Preview/seed/archive pinned demonstration themes; never charge or grant rights.'

    def add_arguments(self, parser):
        parser.add_argument('--snapshot', required=True)
        parser.add_argument('--sha256', required=True)
        parser.add_argument('--action', choices=('preview', 'seed', 'archive'), default='preview')
        parser.add_argument('--confirm', default='')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('G01-D pilot requires PostgreSQL.')
        action = options['action']
        if action != 'preview' and options['confirm'] != 'G01-D-PILOT':
            raise CommandError('Write requires --confirm G01-D-PILOT.')
        try:
            saved = _read_json(options['snapshot'], options['sha256'])
        except (OSError, ValueError) as exc:
            raise CommandError(f'Invalid snapshot: {exc}') from exc
        if (saved.get('kind') != 'G01-D-prechange'
                or saved.get('database_identity') != database_identity()):
            raise CommandError('Snapshot kind or database connection differs.')
        original_slugs = {row['slug'] for row in saved.get('rows', {}).get('themes', [])}
        pilot_slugs = {'tema-' + key for key in PILOT}
        if original_slugs & pilot_slugs:
            raise CommandError('Pilot slug existed before G01-D; reconcile it manually.')

        with transaction.atomic():
            existing = {item.slug: item for item in TbCosmetico.objects.select_for_update()
                        .filter(slug__in=pilot_slugs)}
            if existing and set(existing) != pilot_slugs:
                raise CommandError('Partial pilot catalog; reconcile manually.')
            changed = []
            retained_owned = []
            for key, values in PILOT.items():
                expected, amount = _expected(key, values)
                slug = expected['slug']
                item = existing.get(slug)
                if item:
                    for field, value in expected.items():
                        if field != 'ativo' and getattr(item, field) != value:
                            raise CommandError(f'{slug} changed; reconcile manually ({field}).')
                    offer = CosmeticCheckoutOffer.objects.select_for_update().filter(cosmetico=item).first()
                    if (not offer or offer.amount != amount
                            or (action != 'archive' and not offer.demonstration)):
                        raise CommandError(f'{slug} offer changed; reconcile manually.')
                    if action == 'seed' and (not item.ativo or not offer.active):
                        raise CommandError(f'{slug} is archived; reconcile manually.')
                    has_usage = action == 'archive' and (
                        TbUsuarioCosmetico.objects.filter(cosmetico=item).exists()
                        or CosmeticCheckoutPurchase.objects.filter(cosmetico=item).exists()
                        or CosmeticMMRedemption.objects.filter(cosmetico=item).exists()
                        or EventCosmeticRedemption.objects.filter(cosmetico=item).exists())
                    if has_usage and not item.ativo:
                        raise CommandError(f'{slug} has acquired rights but is inactive.')
                if action == 'seed' and item is None:
                    item = TbCosmetico.objects.create(**expected)
                    CosmeticCheckoutOffer.objects.create(cosmetico=item, amount=amount,
                                                         active=True, demonstration=True)
                    changed.append(slug)
                elif action == 'archive' and item:
                    if has_usage:
                        retained_owned.append(slug)
                    elif item.ativo:
                        item.ativo = False
                        item.save(update_fields=['ativo'])
                        changed.append(slug)
                    if offer.active:
                        offer.active = False
                        offer.save(update_fields=['active'])
                        if slug not in changed:
                            changed.append(slug)
                elif action == 'preview' and item is None:
                    changed.append(slug)
        self.stdout.write(json.dumps({'action': action, 'changed_slugs': changed,
                                      'retained_owned_slugs': retained_owned}, ensure_ascii=False))
