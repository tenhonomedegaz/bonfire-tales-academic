"""Reavalia a primeira ficha apenas quando o fato original gravou essa condição."""
from django.core.management.base import BaseCommand
from django.db import transaction

from home.conquistas import avaliar_primeira_ficha_evento
from home.models import TbEventoConquista


class Command(BaseCommand):
    help = 'Prévia por padrão; --apply concede a primeira ficha com prova no fato canônico.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        facts = TbEventoConquista.objects.filter(
            origem='site', tipo='character_created',
            payload_json__first_character=True,
        ).select_related('conta').order_by('ocorrido_em', 'agregado_id')
        if options['user_id'] is not None:
            facts = facts.filter(conta_id=options['user_id'])
        inspected = awarded = 0
        with transaction.atomic():
            for fact in facts:
                inspected += 1
                awarded += avaliar_primeira_ficha_evento(fact)
            if not options['apply']:
                transaction.set_rollback(True)
        self.stdout.write('%s: fatos=%s concessoes=%s' % (
            'aplicado' if options['apply'] else 'prévia', inspected, awarded))
