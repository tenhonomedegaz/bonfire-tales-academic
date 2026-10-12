"""Reavalia apenas fatos de criação que preservaram a classe inicial."""
from django.core.management.base import BaseCommand
from django.db import transaction

from home.conquistas import avaliar_inicio_classe_evento
from home.models import TbEventoConquista


class Command(BaseCommand):
    help = 'Prévia por padrão; --apply concede inícios de classe com snapshot verificável.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user-id', type=int)

    def handle(self, *args, **options):
        facts = TbEventoConquista.objects.filter(
            origem='site', tipo='character_created'
        ).select_related('conta').order_by('ocorrido_em', 'agregado_id')
        if options['user_id'] is not None:
            facts = facts.filter(conta_id=options['user_id'])
        inspected = awarded = without_snapshot = 0
        if options['apply']:
            for fact in facts:
                inspected += 1
                if not (fact.payload_json or {}).get('initial_class_slug'):
                    without_snapshot += 1
                    continue
                with transaction.atomic():
                    awarded += avaliar_inicio_classe_evento(fact)
        else:
            with transaction.atomic():
                for fact in facts:
                    inspected += 1
                    if not (fact.payload_json or {}).get('initial_class_slug'):
                        without_snapshot += 1
                        continue
                    awarded += avaliar_inicio_classe_evento(fact)
                transaction.set_rollback(True)
        self.stdout.write('%s: fatos=%s sem_snapshot=%s concessoes=%s' % (
            'aplicado' if options['apply'] else 'prévia',
            inspected, without_snapshot, awarded))
