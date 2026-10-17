"""Read-only, lossless pre-change snapshot for the approved G01-D data work."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from home.models import (AsaasCheckoutOrder, CosmeticCheckoutOffer,
                         CosmeticCheckoutPurchase, EventCosmeticOffer,
                         EventCosmeticRedemption, MestreOuroDireito,
                         MestreOuroRevisao, TbCosmetico, TbRecompensaMestre,
                         TbTransacaoMestre, TbUsuarioCosmetico, UserProfile)


def _rows(query, *fields):
    return list(query.order_by('pk').values(*fields))


def database_identity():
    settings = connection.settings_dict
    return {key: str(settings.get(key) or '') for key in ('ENGINE', 'NAME', 'HOST', 'PORT', 'USER')}


def snapshot():
    """Capture original values and immutable references before any D migration."""
    themes = TbCosmetico.objects.filter(tipo='tema')
    theme_ids = list(themes.values_list('pk', flat=True))
    purchases = CosmeticCheckoutPurchase.objects.filter(cosmetico_id__in=theme_ids)
    order_ids = list(purchases.values_list('order_id', flat=True))
    data = {
        'subscription_rewards': _rows(TbRecompensaMestre.objects.filter(tipo='assinatura')),
        'themes': _rows(themes),
        # The demonstration column is added by G01-D (0155). A pre-D snapshot
        # must use only columns present at the 0154 migration head.
        'theme_checkout_offers': _rows(CosmeticCheckoutOffer.objects.filter(cosmetico_id__in=theme_ids),
                                       'id', 'cosmetico_id', 'amount', 'active'),
        'theme_inventory': _rows(TbUsuarioCosmetico.objects.filter(cosmetico_id__in=theme_ids)),
        'theme_purchases': _rows(purchases),
        'related_orders': _rows(AsaasCheckoutOrder.objects.filter(pk__in=order_ids),
                                'id', 'user_id', 'product_code', 'mode', 'amount', 'status',
                                'asaas_payment_id', 'paid_at', 'created_at'),
        'event_offers': _rows(EventCosmeticOffer.objects.filter(cosmetico_id__in=theme_ids)),
        'event_redemptions': _rows(EventCosmeticRedemption.objects.filter(cosmetico_id__in=theme_ids)),
        'lifetime_rights': _rows(MestreOuroDireito.objects.all()),
        'legacy_reviews': _rows(MestreOuroRevisao.objects.all()),
        'mm_ledger': _rows(TbTransacaoMestre.objects.all()),
        'mm_profiles': _rows(UserProfile.objects.all(), 'user_id', 'moedas_mestragem',
                             'mm_ganhas_total', 'mestre_ouro_ativo', 'mestre_ouro_proximo_pgto'),
    }
    return data


class Command(BaseCommand):
    help = 'Export original G01-D rows before an isolated DEV change. Read-only; no apply mode.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True, help='New absolute JSON path outside the repository.')
        parser.add_argument('--expected-home-head', required=True,
                            help='Most recent applied home migration before G01-D changes.')

    def handle(self, *args, **options):
        output = Path(options['output'])
        if not output.is_absolute() or output.suffix.lower() != '.json':
            raise CommandError('Use an absolute .json output path.')
        output = output.resolve()
        repo = Path(__file__).resolve().parents[3]
        if output.is_relative_to(repo):
            raise CommandError('Store the snapshot outside the repository.')
        if not output.parent.is_dir() or output.exists():
            raise CommandError('Output directory must exist and output file must be new.')

        with transaction.atomic():
            if connection.vendor != 'postgresql':
                raise CommandError('G01-D inventory requires PostgreSQL.')
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM django_migrations WHERE app = 'home' ORDER BY id DESC LIMIT 8")
                migrations = cursor.fetchall()
            if not migrations or migrations[0][0] != options['expected_home_head']:
                raise CommandError('home migration head differs from the expected pre-change state.')
            rows = snapshot()
        payload = {
            'kind': 'G01-D-prechange', 'created_at': timezone.now(),
            'database_vendor': connection.vendor,
            'database_name': connection.settings_dict['NAME'],
            'database_identity': database_identity(),
            'recent_home_migrations': [name for (name,) in migrations],
            'counts': {key: len(value) for key, value in rows.items()},
            'restore_policy': ('Restore only explicitly changed catalog/reward fields by primary key '
                               'from this snapshot; preserve purchases, receipts, rights, balances, '
                               'characters and ledgers. Compensate redemptions; never delete receipts.'),
            'rows': rows,
        }
        raw = (json.dumps(payload, ensure_ascii=False, sort_keys=True, cls=DjangoJSONEncoder)
               + '\n').encode('utf-8')
        digest = hashlib.sha256(raw).hexdigest()
        try:
            with output.open('xb') as stream:
                stream.write(raw)
        except FileExistsError as exc:
            raise CommandError('Output file already exists.') from exc
        self.stdout.write(json.dumps({'output': str(output), 'sha256': digest,
                                      'counts': payload['counts']}, ensure_ascii=False))
