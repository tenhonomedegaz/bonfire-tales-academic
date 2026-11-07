"""Preview or apply an explicitly reviewed batch of imported action tags."""

from hashlib import sha256
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from home.bestiary_feature_retag import FeatureRetagConflict, reviewed_statblock
from home.management.commands.importar_bestiario_csv import CSV_PATH, _read_rows, _slug_criatura
from home.models import TbBestiario
from home.tag_engine import Library


class Command(BaseCommand):
    help = 'Confere fonte/identidade/versao e aplica tags de acoes aprovadas.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--csv', default=str(CSV_PATH))
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            source = Path(options['csv'])
            source_hash = sha256(source.read_bytes()).hexdigest()
            manifest = json.loads(Path(options['manifest']).read_text(encoding='utf-8'))
            source_rows = _read_rows(source, [])
        except (OSError, ValueError) as exc:
            raise CommandError(f'Fonte ou manifesto invalido: {exc}') from exc
        if (not isinstance(manifest, dict) or manifest.get('version') != 1 or
                manifest.get('source_sha256') != source_hash or
                not isinstance(manifest.get('rows'), list) or not manifest['rows']):
            raise CommandError('Manifesto nao corresponde ao CSV revisado.')
        by_slug = {}
        for row in source_rows:
            slug = _slug_criatura(row['Name'].strip())
            if slug in by_slug:
                raise CommandError(f'Slug duplicado no CSV: {slug}')
            by_slug[slug] = row
        seen = set()
        updated = already = 0
        library = Library()
        try:
            with transaction.atomic():
                for proposal in manifest['rows']:
                    if not isinstance(proposal, dict):
                        raise FeatureRetagConflict('Proposta invalida.')
                    slug = proposal.get('slug')
                    if not isinstance(slug, str) or slug in seen or slug not in by_slug:
                        raise FeatureRetagConflict('Slug ausente ou repetido.')
                    seen.add(slug)
                    creature = TbBestiario.objects.select_for_update().filter(
                        pk=proposal.get('pk'), slug=slug).first()
                    if creature is None:
                        raise FeatureRetagConflict(f'Criatura ausente: {slug}')
                    revised, changed = reviewed_statblock(
                        creature, by_slug[slug], proposal, library=library)
                    if changed:
                        updated += 1
                        if options['apply']:
                            creature.statblock_json = revised
                            creature.save(update_fields=['statblock_json'])
                    else:
                        already += 1
                if not options['apply']:
                    transaction.set_rollback(True)
        except FeatureRetagConflict as exc:
            raise CommandError(str(exc)) from exc
        mode = 'Aplicado' if options['apply'] else 'Preflight'
        self.stdout.write(f'{mode}: {updated} criaturas a atualizar; {already} ja aplicadas; '
                          f'{sum(len(row["features"]) for row in manifest["rows"])} acoes revisadas.')
