"""Concilia lançamentos explícitos de mesa com fatos de conquistas."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from home.conquistas import avaliar_aventuras_jogadas, registrar_fato_aventura
from home.models import TbEventoConquista, TbPersonagemAventura


class Command(BaseCommand):
    help = ('Prévia por padrão; --apply registra fatos de lançamentos explícitos '
            'e reavalia conquistas sem converter saldos agregados em missões.')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        ledgers = TbPersonagemAventura.objects.filter(
            origem='mesa', revertido=False, qtd_aventuras__gt=0,
        ).select_related('id_personagem').order_by('pk')
        if options['user_id'] is not None:
            ledgers = ledgers.filter(id_personagem__dono_id=options['user_id'])
        inspected = new_facts = 0
        affected_users = set()
        with transaction.atomic():
            for ledger in ledgers.iterator():
                inspected += 1
                affected_users.add(ledger.id_personagem.dono_id)
                existed = TbEventoConquista.objects.filter(
                    origem='site_ledger',
                    chave_origem=f'aventura-ledger:{ledger.pk}:registrada').exists()
                registrar_fato_aventura(ledger, avaliar=False)
                new_facts += int(not existed)
            for user in get_user_model().objects.filter(pk__in=affected_users):
                avaliar_aventuras_jogadas(user)
            if not options['apply']:
                transaction.set_rollback(True)
        self.stdout.write('%s: lancamentos=%s fatos_novos=%s contas=%s' % (
            'aplicado' if options['apply'] else 'prévia',
            inspected, new_facts, len(affected_users)))
