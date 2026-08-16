"""Saneia forma e referencias das descricoes de habilidades de classe."""
from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from home.models import TbClasse, TbClassehabilidade, TbSubclasse


ABILITY_LINK_RE = re.compile(
    r"\[([^\]]+)]\(\s*tbClassehabilidade\s*,\s*([^,()]+?)\s*,\s*([^,()]+?)\s*\)",
    re.IGNORECASE,
)
STANDALONE_EFFECT_RE = re.compile(
    r"(?m)^[ \t]*(?:-[ \t]*)?\*\*Efeito:\*\*[ \t]*(?:\r?\n|$)",
    re.IGNORECASE,
)
LEADING_LABEL_RE = re.compile(
    r"(?m)^([ \t]*)(?:-[ \t]*)?\*\*(?:Custo|Ativa(?:ç|c)ão):\*\*[ \t]*",
    re.IGNORECASE,
)


def _reference_index():
    classes = {item.slug: item for item in TbClasse.objects.all()}
    subclasses = {
        item.slug: item for item in TbSubclasse.objects.select_related('id_classe')
    }
    abilities = {}
    for ability in TbClassehabilidade.objects.select_related('id_classe', 'id_subclasse'):
        owner = ability.id_subclasse.slug if ability.id_subclasse_id else ability.id_classe.slug
        abilities.setdefault((owner, slugify(ability.nome)), []).append(ability)
    return classes, subclasses, abilities


def sanitize_description(description, *, source=None, index=None):
    """Retorna ``(texto, contadores, avisos)`` sem alterar regra narrativa.

    Links quebrados e links para registros exclusivos de tabela viram texto
    comum. Referencias para outra classe ou uma subclasse irma tambem viram
    texto: o nome reaproveitado nao identifica a habilidade mecanica da fonte.
    """
    text = description or ''
    counters = {'labels': 0, 'invalid_links': 0, 'table_only_links': 0,
                'cross_owner_links': 0}
    warnings = []

    text, count = STANDALONE_EFFECT_RE.subn('', text)
    counters['labels'] += count
    text, count = LEADING_LABEL_RE.subn(r'\1', text)
    counters['labels'] += count

    classes, subclasses, abilities = index or _reference_index()

    def replace(match):
        label, owner, ability_slug = match.groups()
        owner = owner.strip()
        ability_slug = ability_slug.strip()
        targets = abilities.get((owner, ability_slug), [])
        if not targets or (owner not in classes and owner not in subclasses):
            counters['invalid_links'] += 1
            return label
        visible = [target for target in targets if not target.table_only]
        if not visible:
            counters['table_only_links'] += 1
            return label
        target = visible[0]
        if source is not None:
            cross_class = target.id_classe_id != source.id_classe_id
            sibling_subclass = (
                source.id_subclasse_id and target.id_subclasse_id
                and source.id_subclasse_id != target.id_subclasse_id)
            if cross_class or sibling_subclass:
                counters['cross_owner_links'] += 1
                return label
        return match.group(0)

    text = ABILITY_LINK_RE.sub(replace, text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text, counters, warnings


class Command(BaseCommand):
    help = (
        'Remove rotulos editoriais e links quebrados/table-only das habilidades; '
        'referencias cruzadas validas sao somente reportadas.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        index = _reference_index()
        totals = {'abilities': 0, 'labels': 0, 'invalid_links': 0,
                  'table_only_links': 0, 'cross_owner_links': 0}
        warnings = []
        for ability in TbClassehabilidade.objects.select_related(
                'id_classe', 'id_subclasse').order_by('id_habilidade'):
            cleaned, counters, found_warnings = sanitize_description(
                ability.descricao, source=ability, index=index)
            for key, value in counters.items():
                totals[key] += value
            warnings.extend(found_warnings)
            if cleaned != (ability.descricao or ''):
                ability.descricao = cleaned
                ability.save(update_fields=['descricao'])
                totals['abilities'] += 1

        if options['check']:
            transaction.set_rollback(True)
        suffix = ' (simulacao)' if options['check'] else ''
        message = ('Descricoes saneadas%s: ' % suffix) + (
            '%(abilities)d habilidades, %(labels)d rotulos, '
            '%(invalid_links)d links invalidos, %(table_only_links)d links table-only, '
            '%(cross_owner_links)d links de outra origem.'
            % totals)
        self.stdout.write(self.style.SUCCESS(message))
        if warnings:
            self.stdout.write('Referencias cruzadas validas para revisao: %d' % len(warnings))
            for warning in sorted(set(warnings)):
                self.stdout.write('  ' + warning)
