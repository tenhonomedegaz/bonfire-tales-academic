"""Prepara somente a fixture; a publicação usa o sync_conteudo existente."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def prepare_fixture(text, reference):
    """Upsert pela identidade EN, preservando PK, slug e bytes de outros registros."""
    records = json.loads(text)
    spells = [row for row in records if row['model'] == 'home.tbmagia']
    matches = [row for row in spells
               if (row['fields'].get('nome_ingles') or '').strip().casefold()
               == 'battle familiar']
    if len(matches) > 1:
        raise ValueError('Identidade Battle Familiar duplicada na fixture.')
    familiar = [row for row in spells
                if (row['fields'].get('nome_ingles') or '').strip().casefold()
                == 'find familiar']
    if len(familiar) != 1:
        raise ValueError('Find Familiar deve resolver para exatamente um registro existente.')
    old = matches[0] if matches else None
    slug = old['fields']['slug'] if old else 'familiar-de-batalha'
    if any(row is not old and (row['fields']['slug'] == slug
           or row['fields']['nome'].casefold() == 'familiar de batalha') for row in spells):
        raise ValueError('Colisão de nome/slug sem identidade EN Battle Familiar.')
    classes = {row['fields']['slug'] for row in records if row['model'] == 'home.tbclasse'}
    # O catálogo Bonfire chama a classe Warlock/Bruxo de Místico.
    if not {'druida', 'mistico', 'mago'} <= classes:
        raise ValueError('Classes Druida, Místico (Bruxo) e Mago obrigatórias.')
    description, higher = reference.split('Você conjura um familiar', 1)[1].split(
        '## Usando um espaço de magia de círculo superior', 1)
    description = 'Você conjura um familiar' + description.rstrip()
    higher = higher.split('## Notas de fidelidade e integração', 1)[0].strip()
    fields = dict(
        nome='Familiar de Batalha', nome_ingles='Battle Familiar', slug=slug,
        nivel=2, casting_time='Ação', ritual=False, duracao='1 hora',
        concentracao=False, escola='Conjuração', alcance='3 metros (10 pés)',
        componentes='V, S, M (um diamante no valor de pelo menos 25 PO)',
        classes='Druida, Bruxo, Mago', classes_slugs=['druida', 'mistico', 'mago'],
        descricao=description, em_niveis_superiores=higher,
        tags_json=['log_castable'],
    )
    row = dict(model='home.tbmagia', pk=old['pk'] if old else
               max(row['pk'] for row in spells) + 1, fields=fields)
    newline = '\r\n' if '\r\n' in text else '\n'
    encoded = json.dumps(row, ensure_ascii=False, indent=2).replace('\n', newline)
    if old:
        decoder = json.JSONDecoder()
        pos = text.index('[') + 1
        while True:
            while text[pos].isspace() or text[pos] == ',':
                pos += 1
            value, end = decoder.raw_decode(text, pos)
            if value == old:
                return text[:pos] + encoded + text[end:]
            pos = end
    end = text.rindex(']')
    return text[:end].rstrip() + ',' + newline + encoded + newline + text[end:]


class Command(BaseCommand):
    help = 'Cadastra Battle Familiar na fixture por identidade EN, sem acessar banco.'

    def add_arguments(self, parser):
        parser.add_argument('--fixture', type=Path,
                            default=Path(settings.BASE_DIR) / 'home/fixtures/conteudo.json')
        parser.add_argument('--reference', type=Path,
                            default=Path(settings.BASE_DIR) / 'ref/FAMILIAR_DE_BATALHA.md')

    def handle(self, *args, **options):
        path = options['fixture']
        try:
            original = path.read_bytes().decode('utf-8')
            result = prepare_fixture(original, options['reference'].read_text(encoding='utf-8'))
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        if result != original:
            path.write_bytes(result.encode('utf-8'))
        self.stdout.write('Battle Familiar: fixture atualizada.' if result != original
                          else 'Battle Familiar: fixture já atualizada (idempotente).')
