"""Preview or apply an audited bestiary spell-reference batch to PostgreSQL."""

from hashlib import sha256
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.bestiary_audit import audit_snapshot
from home.bestiary_repair import RepairConflict, reconcile_snapshot
from home.models import TbBestiario, TbMagia


class Command(BaseCommand):
    help = 'Confere um lote auditado no catálogo; --apply grava somente os statblocks conferidos.'

    def add_arguments(self, parser):
        parser.add_argument('--backup', required=True)
        parser.add_argument('--audit', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            raw = Path(options['backup']).read_bytes()
            source_rows = json.loads(raw)
            report = json.loads(Path(options['audit']).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Entrada inválida: {exc}') from exc
        if not isinstance(source_rows, list) or not isinstance(report, dict):
            raise CommandError('Backup ou auditoria inválidos.')
        source = report.get('source')
        if not isinstance(source, dict) or source.get('sha256') != sha256(raw).hexdigest():
            raise CommandError('O hash do backup não corresponde à auditoria.')
        candidates = report.get('repair_candidates')
        if not isinstance(candidates, list) or candidates != audit_snapshot(source_rows)['repair_candidates']:
            raise CommandError('Candidatos não correspondem à auditoria reproduzida do backup.')
        creature_pks = {item.get('creature_pk') for item in candidates}
        spell_pks = {item.get('spell_pk') for item in candidates}
        if any(not isinstance(pk, int) or isinstance(pk, bool) for pk in creature_pks | spell_pks):
            raise CommandError('PK de candidato inválida.')

        with transaction.atomic():
            creatures = list(TbBestiario.objects.select_for_update().filter(
                pk__in=creature_pks).order_by('pk'))
            spells = list(TbMagia.objects.filter(pk__in=spell_pks).order_by('pk'))
            # Include the whole spell namespace: normalized aliases must be unique.
            spell_rows = [
                {'model': 'home.tbmagia', 'pk': pk, 'fields': {'slug': slug}}
                for pk, slug in TbMagia.objects.values_list('pk', 'slug')
            ]
            current_rows = spell_rows + [
                {'model': 'home.tbbestiario', 'pk': creature.pk,
                 'fields': {'slug': creature.slug, 'statblock_json': creature.statblock_json}}
                for creature in creatures
            ]
            if len(creatures) != len(creature_pks) or len(spells) != len(spell_pks):
                raise CommandError('Criatura ou magia do lote ausente no catálogo.')
            try:
                reconciled, counts = reconcile_snapshot(current_rows, report)
            except RepairConflict as exc:
                raise CommandError(f'Catálogo diverge da auditoria: {exc}') from exc
            if options['apply']:
                by_pk = {row['pk']: row for row in reconciled
                         if row['model'] == 'home.tbbestiario'}
                for creature in creatures:
                    changed = by_pk[creature.pk]['fields']['statblock_json']
                    if changed != creature.statblock_json:
                        creature.statblock_json = changed
                        creature.save(update_fields=['statblock_json'])
        mode = 'Aplicado' if options['apply'] else 'Prévia sem escrita'
        self.stdout.write(f"{mode}: reparos={counts['applied']}; "
                          f"já aplicados={counts['unchanged']}; criaturas={len(creatures)}.")
