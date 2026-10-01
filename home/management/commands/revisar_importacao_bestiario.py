"""Review exact CSV-to-catalog differences before updating existing creatures."""

from hashlib import sha256
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from home.management.commands.importar_bestiario_csv import (
    CSV_PATH, SECOES, _fields_for_row, _load_spell_alignment, _read_rows,
    _resolve_spell_alignment, _slug_criatura, _spell_catalog,
    _split_secao,
)
from home.models import TbBestiario


REVIEW_FIELDS = (
    'nome', 'tipo', 'tamanho', 'nd', 'alinhamento', 'ca', 'pv',
    'statblock_json', 'tags_json', 'descricao_markdown',
)
SOURCE_METADATA_FIELDS = {
    'name_en': 'Name', 'size_en': 'Size',
    'type_en': 'Type', 'alignment_en': 'Alignment',
}


def _digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, cls=DjangoJSONEncoder,
                     separators=(',', ':')).encode('utf-8')
    return sha256(raw).hexdigest()


def _current_snapshot(creature):
    return {field.name: getattr(creature, field.attname)
            for field in creature._meta.concrete_fields}


def _approved_name_projection(creature, name):
    """Rename the three public labels without importing unrelated statblock data."""
    old = creature.nome
    statblock = creature.statblock_json
    description = creature.descricao_markdown
    heading = f'### {old}'
    if (not isinstance(statblock, dict) or statblock.get('name') not in (old, name) or
            not isinstance(description, str) or
            description.split('\n', 1)[0] not in (heading, f'### {name}')):
        raise CommandError(f'Titulos divergentes: {creature.slug}')
    updated = {**statblock, 'name': name}
    revised = f'### {name}' + description[len(description.split('\n', 1)[0]):]
    return updated, revised


def _source_identity_issue(creature, row):
    """Require the CSV identity and feature boundaries before touching source metadata."""
    sb = creature.statblock_json
    if not isinstance(sb, dict) or creature.comunidade or creature.autor_id:
        return 'registro_nao_importado_ou_editado'
    if (creature.nd or '') != str(row.get('CR') or '').strip():
        return 'nd_divergente'
    for csv_key, json_key, _ in SECOES:
        current = sb.get(json_key) or []
        if not isinstance(current, list) or any(not isinstance(item, dict) for item in current):
            return f'{json_key}_invalido'
        source_names = [item['name_en'] for item in _split_secao(row.get(csv_key), {})]
        if [item.get('name_en') for item in current] != source_names:
            return f'{json_key}_divergente'
    return None


def _source_metadata_proposal(creature, row):
    sb = creature.statblock_json
    return {field: str(row.get(column) or '').strip()
            for field, column in SOURCE_METADATA_FIELDS.items()
            if sb.get(field) != str(row.get(column) or '').strip()}


def _review_source_metadata(command, source, source_hash, by_slug, options):
    """Review/apply only source-language keys, retaining every translated or manual field."""
    apply = options['apply']
    if apply and (not options['manifest'] or options['output'] or options['slugs']):
        raise CommandError('--apply requer --manifest, sem --output/--slugs.')
    if not apply and (not options['output'] or options['manifest']):
        raise CommandError('Preview requer --output, sem --manifest.')
    if not apply:
        selected = options['slugs'] or list(TbBestiario.objects.values_list('slug', flat=True))
        if len(selected) != len(set(selected)):
            raise CommandError('Slugs repetidos.')
        rows, pending = [], []
        for slug in selected:
            creature = TbBestiario.objects.filter(slug=slug).first()
            if not creature:
                pending.append({'slug': slug, 'reason': 'registro_ausente'})
                continue
            source_row = by_slug.get(slug)
            if not source_row:
                if options['slugs'] or (isinstance(creature.statblock_json, dict) and
                                        creature.statblock_json.get('name_en')):
                    pending.append({'slug': slug, 'reason': 'fonte_ausente'})
                continue
            issue = _source_identity_issue(creature, source_row)
            if issue:
                pending.append({'slug': slug, 'reason': issue})
                continue
            proposed = _source_metadata_proposal(creature, source_row)
            if proposed:
                rows.append({'pk': creature.pk, 'slug': slug,
                             'current_statblock_sha256': _digest(creature.statblock_json),
                             'proposed_fields': proposed, 'approved_fields': []})
        target = Path(options['output']).resolve()
        if target == source or target.exists():
            raise CommandError('Saida deve ser arquivo novo, separado do CSV.')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8') as handle:
            json.dump({'version': 2, 'mode': 'source_metadata',
                       'source_sha256': source_hash, 'rows': rows, 'pending': pending},
                      handle, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
            handle.write('\n')
        command.stdout.write(f'Preview metadados de origem: {len(rows)} propostas; '
                             f'{len(pending)} pendencias; {target}')
        return

    try:
        manifest = json.loads(Path(options['manifest']).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CommandError(f'Manifesto invalido: {exc}') from exc
    if (not isinstance(manifest, dict) or manifest.get('version') != 2 or
            manifest.get('mode') != 'source_metadata' or
            manifest.get('source_sha256') != source_hash or
            not isinstance(manifest.get('rows'), list)):
        raise CommandError('Manifesto nao corresponde ao CSV revisado.')
    updated = unchanged = 0
    seen = set()
    with transaction.atomic():
        for item in manifest['rows']:
            if not isinstance(item, dict):
                raise CommandError('Entrada invalida no manifesto.')
            slug = item.get('slug')
            approved = item.get('approved_fields')
            if (not isinstance(slug, str) or slug in seen or slug not in by_slug or
                    not isinstance(item.get('pk'), int) or isinstance(item['pk'], bool) or
                    not isinstance(approved, list) or
                    any(not isinstance(field, str) for field in approved) or
                    len(approved) != len(set(approved)) or
                    any(field not in SOURCE_METADATA_FIELDS for field in approved)):
                raise CommandError(f'Identidade ou aprovacao invalida: {slug}')
            seen.add(slug)
            if not approved:
                continue
            creature = TbBestiario.objects.select_for_update().filter(pk=item['pk'], slug=slug).first()
            if not creature or _source_identity_issue(creature, by_slug[slug]):
                raise CommandError(f'Identidade divergente: {slug}')
            expected = _source_metadata_proposal(creature, by_slug[slug])
            original_proposal = item.get('proposed_fields')
            if (not isinstance(original_proposal, dict) or
                    any(field not in SOURCE_METADATA_FIELDS for field in original_proposal) or
                    any(field not in original_proposal for field in approved) or
                    any(original_proposal[field] != str(by_slug[slug].get(column) or '').strip()
                        for field, column in SOURCE_METADATA_FIELDS.items()
                        if field in original_proposal)):
                raise CommandError(f'Proposta adulterada: {slug}')
            if all(field not in expected for field in approved):
                unchanged += 1
                continue
            if _digest(creature.statblock_json) != item.get('current_statblock_sha256'):
                raise CommandError(f'Criatura mudou desde a revisao: {slug}')
            revised = {**creature.statblock_json}
            for field in approved:
                revised[field] = original_proposal[field]
            creature.statblock_json = revised
            creature.save(update_fields=['statblock_json'])
            updated += 1
    command.stdout.write(f'Aplicado: {updated}; ja aplicado: {unchanged}; '
                         f'sem aprovacao: {len(manifest["rows"]) - updated - unchanged}.')


class Command(BaseCommand):
    help = 'Gera diferencas revisaveis ou aplica apenas campos aprovados, com preflight atomico.'

    def add_arguments(self, parser):
        parser.add_argument('--csv', default=str(CSV_PATH))
        parser.add_argument('--slugs', nargs='*', default=[])
        parser.add_argument('--output', help='JSON novo para revisao; approved_fields inicia vazio.')
        parser.add_argument('--manifest', help='JSON revisado que sera aplicado.')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--source-metadata', action='store_true',
                            help='Revisar apenas name_en/size_en/type_en/alignment_en contra o CSV.')

    def handle(self, *args, **options):
        apply = options['apply']
        if apply and (not options['manifest'] or options['output'] or options['slugs']):
            raise CommandError('--apply requer --manifest, sem --output/--slugs.')
        if not apply and (not options['output'] or options['manifest']):
            raise CommandError('Preview requer --output, sem --manifest.')
        source = Path(options['csv']).resolve()
        try:
            source_hash = sha256(source.read_bytes()).hexdigest()
            rows = _read_rows(source, [])
        except (OSError, ValueError) as exc:
            raise CommandError(f'CSV invalido: {exc}') from exc
        by_slug = {}
        for row in rows:
            slug = _slug_criatura(row['Name'].strip())
            if slug in by_slug:
                raise CommandError(f'Slug repetido no CSV: {slug}')
            by_slug[slug] = row
        if options['source_metadata']:
            return _review_source_metadata(self, source, source_hash, by_slug, options)
        catalog = _spell_catalog(_resolve_spell_alignment(_load_spell_alignment()))

        if not apply:
            selected = options['slugs'] or list(by_slug)
            unknown = set(selected) - set(by_slug)
            if unknown or len(selected) != len(set(selected)):
                raise CommandError(f'Slugs ausentes ou repetidos: {sorted(unknown)}')
            review = []
            for slug in selected:
                creature = TbBestiario.objects.filter(slug=slug).first()
                if not creature:
                    continue  # Importador aditivo cuida de criaturas novas.
                _, fields = _fields_for_row(by_slug[slug], catalog)
                proposed = {key: fields[key] for key in REVIEW_FIELDS}
                changes = {key: {'current': getattr(creature, key), 'proposed': proposed[key]}
                           for key in REVIEW_FIELDS if getattr(creature, key) != proposed[key]}
                review.append({
                    'pk': creature.pk, 'slug': slug,
                    'name_en': by_slug[slug]['Name'].strip(),
                    'current_sha256': _digest(_current_snapshot(creature)),
                    'proposed_sha256': _digest(proposed),
                    'blocked': bool(creature.comunidade or creature.autor_id),
                    'changes': changes, 'approved_fields': [],
                })
            target = Path(options['output']).resolve()
            if target == source or target.exists():
                raise CommandError('Saida deve ser arquivo novo, separado do CSV.')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x', encoding='utf-8') as handle:
                json.dump({'version': 1, 'source_sha256': source_hash, 'rows': review},
                          handle, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
                handle.write('\n')
            self.stdout.write(f'Preview: {len(review)} criaturas existentes; '
                              f'{sum(bool(item["changes"]) for item in review)} com diferencas; {target}')
            return

        try:
            manifest = json.loads(Path(options['manifest']).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Manifesto invalido: {exc}') from exc
        if (not isinstance(manifest, dict) or manifest.get('version') != 1 or
                manifest.get('source_sha256') != source_hash or
                not isinstance(manifest.get('rows'), list)):
            raise CommandError('Manifesto nao corresponde ao CSV revisado.')

        updated = unchanged = 0
        seen = set()
        with transaction.atomic():
            for item in manifest['rows']:
                if not isinstance(item, dict):
                    raise CommandError('Entrada invalida no manifesto.')
                slug = item.get('slug')
                if not isinstance(slug, str) or slug in seen or slug not in by_slug:
                    raise CommandError(f'Slug duplicado ou ausente no CSV: {slug}')
                seen.add(slug)
                if not isinstance(item.get('pk'), int) or isinstance(item['pk'], bool):
                    raise CommandError(f'PK invalida no manifesto: {slug}')
                approvals = item.get('approved_fields')
                changes = item.get('changes')
                if (not isinstance(approvals, list) or
                        any(not isinstance(key, str) for key in approvals) or
                        len(approvals) != len(set(approvals)) or
                        not isinstance(changes, dict) or
                        any(key not in REVIEW_FIELDS for key in changes) or
                        any(key not in changes or not isinstance(changes[key], dict)
                            for key in approvals)):
                    raise CommandError(f'Campos aprovados invalidos: {slug}')
                if not approvals:
                    continue
                if item.get('blocked'):
                    raise CommandError(f'Criatura da comunidade/autoria nao pode ser atualizada: {slug}')
                creature = TbBestiario.objects.select_for_update().filter(pk=item.get('pk')).first()
                if (not creature or creature.slug != slug or creature.comunidade or creature.autor_id):
                    raise CommandError(f'Identidade divergente: {slug}')
                _, fields = _fields_for_row(by_slug[slug], catalog)
                proposed = {key: fields[key] for key in REVIEW_FIELDS}
                if _digest(proposed) != item.get('proposed_sha256'):
                    raise CommandError(f'Proposta mudou desde a revisao: {slug}')
                if any(changes[key].get('proposed') != proposed[key] for key in approvals):
                    raise CommandError(f'Campo revisado diverge da proposta: {slug}')
                if 'nome' in approvals and ({'statblock_json', 'descricao_markdown'} & set(approvals)):
                    raise CommandError(f'Aprovar nome separadamente das projecoes completas: {slug}')
                already_applied = all(getattr(creature, key) == proposed[key] for key in approvals)
                name_projection = None
                if already_applied and 'nome' in approvals:
                    name_projection = _approved_name_projection(creature, proposed['nome'])
                    already_applied = (already_applied and
                                       creature.statblock_json == name_projection[0] and
                                       creature.descricao_markdown == name_projection[1])
                if already_applied:
                    unchanged += 1
                    continue
                if _digest(_current_snapshot(creature)) != item.get('current_sha256'):
                    raise CommandError(f'Criatura mudou desde a revisao: {slug}')
                if 'nome' in approvals and name_projection is None:
                    name_projection = _approved_name_projection(creature, proposed['nome'])
                for key in approvals:
                    setattr(creature, key, proposed[key])
                update_fields = list(approvals)
                if name_projection:
                    creature.statblock_json, creature.descricao_markdown = name_projection
                    update_fields += ['statblock_json', 'descricao_markdown']
                creature.save(update_fields=update_fields)
                updated += 1
        self.stdout.write(f'Aplicado: {updated}; ja aplicado: {unchanged}; '
                          f'sem aprovacao: {len(manifest["rows"]) - updated - unchanged}.')
