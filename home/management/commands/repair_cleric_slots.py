"""Prévia e aplicação explícita do reparo de conteúdo Q04."""
import json

from django.core.management.base import BaseCommand, CommandError

from home.cleric_slot_repair import SlotRepairConflict, repair_cleric_slots


class Command(BaseCommand):
  help = 'Relata reparo Q04; --apply exige integridade/backup/autorização do banco alvo previamente conferidos.'

  def add_arguments(self, parser):
    parser.add_argument('--apply', action='store_true', help='Aplica o lote conhecido atomicamente.')

  def handle(self, *args, **options):
    try:
      report = repair_cleric_slots(apply=options['apply'])
    except SlotRepairConflict as error:
      raise CommandError(str(error)) from error
    self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
