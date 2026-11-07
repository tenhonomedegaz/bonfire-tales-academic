"""Prévia e aplicação explícita da mecânica Q07 no conteúdo conhecido."""
import json

from django.core.management.base import BaseCommand, CommandError

from home.primal_order_repair import PrimalOrderConflict, repair_primal_order


class Command(BaseCommand):
  help = 'Completa Q07; --apply requer integridade, backup e autorização conferidos no banco alvo.'

  def add_arguments(self, parser):
    parser.add_argument('--apply', action='store_true')

  def handle(self, *args, **options):
    try:
      result = repair_primal_order(apply=options['apply'])
    except PrimalOrderConflict as error:
      raise CommandError(str(error)) from error
    self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
