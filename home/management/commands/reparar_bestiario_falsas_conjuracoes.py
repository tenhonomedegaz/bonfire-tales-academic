"""Preview and atomically repair audited false spellcasting tags in existing creatures."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from home.bestiary_false_casts import repair_false_casts
from home.management.commands.revisar_importacao_bestiario import _current_snapshot, _digest
from home.models import TbBestiario


def _proposal(creature):
    statblock, tags, description, edits = repair_false_casts(
        creature.statblock_json, creature.tags_json, creature.descricao_markdown)
    if not edits:
        return None
    snapshot = _current_snapshot(creature)
    after = {**snapshot, 'statblock_json': statblock, 'tags_json': tags,
             'descricao_markdown': description}
    return {
        'pk': creature.pk, 'slug': creature.slug, 'current_sha256': _digest(snapshot),
        'proposed_sha256': _digest(after), 'edits': edits,
    }


class Command(BaseCommand):
    help = 'Revisa e corrige falsas tags de conjuração com hashes e aplicação atômica.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Gera arquivo JSON novo, sem escrita no banco.')
        parser.add_argument('--manifest', help='Arquivo JSON de prévia a aplicar.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if options['apply']:
            if not options['manifest'] or options['output']:
                raise CommandError('--apply requer --manifest, sem --output.')
            try:
                manifest = json.loads(Path(options['manifest']).read_text(encoding='utf-8'))
            except (OSError, ValueError) as exc:
                raise CommandError(f'Manifesto inválido: {exc}') from exc
            if (not isinstance(manifest, dict) or manifest.get('version') != 1 or
                    not isinstance(manifest.get('rows'), list)):
                raise CommandError('Formato de manifesto inválido.')
            updated = unchanged = 0
            seen = set()
            with transaction.atomic():
                for row in manifest['rows']:
                    if not isinstance(row, dict) or not isinstance(row.get('pk'), int) or isinstance(row.get('pk'), bool):
                        raise CommandError('Entrada ou PK inválida.')
                    if row['pk'] in seen:
                        raise CommandError('PK duplicada no manifesto.')
                    seen.add(row['pk'])
                    creature = TbBestiario.objects.select_for_update().filter(pk=row['pk']).first()
                    if (not creature or creature.slug != row.get('slug') or
                            creature.comunidade or creature.autor_id):
                        raise CommandError(f'Identidade ou autoria divergente: {row.get("slug")}')
                    current_hash = _digest(_current_snapshot(creature))
                    if current_hash == row.get('proposed_sha256'):
                        unchanged += 1
                        continue
                    if current_hash != row.get('current_sha256'):
                        raise CommandError(f'Criatura mudou desde a prévia: {creature.slug}')
                    proposal = _proposal(creature)
                    if (proposal is None or proposal != row or
                            proposal['current_sha256'] == proposal['proposed_sha256']):
                        raise CommandError(f'Reparo diverge da prévia: {creature.slug}')
                    statblock, tags, description, _ = repair_false_casts(
                        creature.statblock_json, creature.tags_json, creature.descricao_markdown)
                    creature.statblock_json = statblock
                    creature.tags_json = tags
                    creature.descricao_markdown = description
                    creature.save(update_fields=['statblock_json', 'tags_json', 'descricao_markdown'])
                    updated += 1
            self.stdout.write(f'Aplicado: {updated}; já aplicado: {unchanged}.')
            return

        if not options['output'] or options['manifest']:
            raise CommandError('Prévia requer --output, sem --manifest.')
        target = Path(options['output']).resolve()
        if target.exists():
            raise CommandError('Arquivo de saída já existe.')
        rows = []
        for creature in TbBestiario.objects.filter(comunidade=False, autor__isnull=True).order_by('pk'):
            proposal = _proposal(creature)
            if proposal:
                rows.append(proposal)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            json.dump({'version': 1, 'rows': rows}, handle, ensure_ascii=False,
                      indent=2, cls=DjangoJSONEncoder)
            handle.write('\n')
        self.stdout.write(f'Prévia: {len(rows)} criaturas; '
                          f'{sum(len(row["edits"]) for row in rows)} traços; {target}')
