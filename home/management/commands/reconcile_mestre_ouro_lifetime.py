"""Preview and explicitly apply the historical first-purchase transition."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from home.mestre_ouro import reconcile_mestre_ouro
from home.models import MestreOuroDireito, TbTransacaoMestre


class Command(BaseCommand):
    help = 'Audit legacy MM purchases; apply only with explicit PO authorization.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--confirm', default='')
        parser.add_argument('--actor', default='')

    def handle(self, *args, **options):
        if options['apply']:
            actor = get_user_model().objects.filter(username=options['actor']).first()
            if (options['confirm'] != 'MESTRE_OURO_VITALICIO' or actor is None
                    or not actor.is_active or not actor.is_superuser):
                raise CommandError('Apply requires active superuser and explicit confirmation.')
        user_ids = (get_user_model().objects.filter(
            Q(profile__mestre_ouro_ativo=True)
            | Q(transacoes_mm__tipo__in=('assinatura', 'mensalidade'))
        ).distinct().order_by('pk').values_list('pk', flat=True))
        rows = []
        for user_id in user_ids:
            purchases = list(TbTransacaoMestre.objects.filter(
                mestre_id=user_id, tipo='assinatura', valor_mm__lt=0,
            ).order_by('criado_em', 'pk').values_list('pk', flat=True)[:2])
            has_grant = MestreOuroDireito.objects.filter(user_id=user_id).exists()
            legacy_active = get_user_model().objects.filter(
                pk=user_id, profile__mestre_ouro_ativo=True).exists()
            monthly = TbTransacaoMestre.objects.filter(
                mestre_id=user_id, tipo='mensalidade', valor_mm__lt=0).exists()
            if options['apply']:
                _, result = reconcile_mestre_ouro(user_id)
            else:
                result = ('already_granted' if has_grant else 'eligible' if len(purchases) == 1
                          else 'review_required' if len(purchases) > 1 or legacy_active or monthly
                          else 'unproven')
            rows.append({'user_id': user_id, 'first_purchase_id': purchases[0] if purchases else None,
                         'status': result})
        self.stdout.write(json.dumps({'mode': 'apply' if options['apply'] else 'preview_only',
                                      'rows': rows}, ensure_ascii=False))
