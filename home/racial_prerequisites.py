"""Mechanical prerequisites after the racial pool's identity/policy gates."""
import re
from functools import lru_cache
from types import SimpleNamespace


def prerequisite_filter(person, borrowed_races=(), *, ruleset=None):
    from . import views
    from .character_engine import derive, magias_concedidas
    ruleset = ruleset or views._resource_ruleset(person)
    origins = None
    if ruleset is not None and 'origin-catalog' in ruleset.manifest:
        from .versioned_origins import VersionedOrigins
        frozen = VersionedOrigins(ruleset)
        if frozen.data['schema'] >= 2:
            origins = frozen
    sheet = derive(person, ruleset=ruleset)
    context = views._talento_prereq_contexto(person, sheet)
    context['owned'].update(views._prereq_label(row['nome'])
                            for row in sheet.get('features', []) if row.get('nome'))
    spell_state = None

    @lru_cache(maxsize=1)
    def qualifier_choices():
        from .character_engine import _collect_escolhas, _features_do_personagem
        _first, values = _collect_escolhas(person, _features_do_personagem(person, ruleset=ruleset))
        return {views._prereq_label(key): {views._prereq_label(value) for value in entries}
                for key, entries in values.items()}

    def qualifier_clause(clause):
        match = re.fullmatch(r'(nao (?:ter|possuir) )?(alento|descendencia)(?: de)? (.+)',
                             views._prereq_label(clause))
        if not match:
            return None
        negative, kind, values = match.groups()
        # Keep the qualifier and negation scoped over the entire alternatives list.
        alternatives = re.split(r'\s+ou\s+', values)
        if any(not re.fullmatch(r'[a-z0-9 -]+', value) for value in alternatives):
            return False
        selected = qualifier_choices().get(kind, set())
        found = any(value in selected for value in alternatives)
        return not found if negative else found

    @lru_cache(maxsize=None)
    def lineages(race_id):
        from .models import TbLinhagem
        if origins is not None:
            return [row for row in origins.objects(TbLinhagem) if row.id_raca_id == race_id]
        return list(TbLinhagem.objects.filter(id_raca_id=race_id)) if race_id else []

    @lru_cache(maxsize=None)
    def origin(model, pk):
        if not pk:
            return None
        if origins is not None:
            return next((row for row in origins.objects(model) if row.pk == pk), None)
        return model.objects.get(pk=pk)

    @lru_cache(maxsize=1)
    def has_slots():
        return bool(views._magias_sheet_info(person, sheet, [], ruleset=ruleset).get('slots'))

    def spells():
        nonlocal spell_state
        if spell_state is None:
            from .models import TbMagia
            from .versioned_spells import spell_catalog
            catalog = (list(spell_catalog(ruleset).values()) if ruleset else list(TbMagia.objects.all()))
            staged = getattr(person, '_pathbuilder_staged_spell_keys', set())
            allowed = {}
            if staged:
                from .pathbuilder_spells import spell_sources
                allowed = {source['pc'].id_classe.nome: source['allowed']
                           for source in spell_sources(person, ruleset=ruleset)}
            known = {views._prereq_label(row.nome) for row in person.magias.all()
                     if (row.id_magia_id, row.origem) not in staged
                     or row.id_magia_id in allowed.get(row.origem, set())}
            slugs = {row['slug'] for row in magias_concedidas(person, ruleset=ruleset)['concedidas']}
            innate = views._innate_spell_uses(person, sheet, ruleset=ruleset)
            unlimited = {slug for (_origin, slug), meta in innate.items() if meta.get('reset') == 'at-will'}
            slugs.update(unlimited)
            available = [spell for spell in catalog if spell.slug in slugs or views._prereq_label(spell.nome) in known]
            spell_state = (available, unlimited)
        return spell_state

    def identity(atom, source):
        from .models import TbEssencia, TbLinhagem, TbRaca
        race = origin(TbRaca, source.id_raca_id)
        if race and atom == views._prereq_label(race.nome):
            # The caller has already checked native or explicit count_as membership.
            return True
        clean = re.sub(r'^(?:qualquer|apenas)\s+', '', atom)
        if clean.startswith(('linhagem', 'linhagens')):
            lineage = origin(TbLinhagem, person.id_linhagem_id)
            if not lineage:
                return False
            label = re.sub(r'^linhagens?\s*', '', clean)
            for candidate in lineages(source.id_raca_id):
                names = {views._prereq_label(candidate.slug),
                         views._prereq_label(candidate.nome.split('(')[0])}
                if label in names:
                    return lineage.pk == candidate.pk
            return bool(race and lineage.id_raca_id == race.pk)
        if clean.startswith('essencia'):
            essence = origin(TbEssencia, person.id_essencia_id)
            label = re.sub(r'^essencia\s*', '', clean)
            return bool(essence and (not label or label in {
                views._prereq_label(essence.slug), views._prereq_label(essence.nome)}))
        if clean.startswith('cultura adotada'):
            return bool(race and race.slug in borrowed_races)
        return None

    def atom_ok(atom, source, ficha):
        atom = views._prereq_label(atom)
        matched = identity(atom, source)
        if matched is not None:
            return matched
        qualified = qualifier_clause(atom)
        if qualified is not None:
            return qualified
        if atom.startswith(('polo ', 'vertente ', 'cla ')):
            value = atom.split(' ', 1)[1]
            return any(value in choice['values'] for choice in context['choices'])
        if atom in {'classe com conjuracao', 'capacidade de conjurar magias usando espacos de magia'}:
            return has_slots()
        if atom == 'capacidade de conjurar ao menos uma magia que exija jogada de ataque':
            return any(re.search(r'\battack\s*:\s*magic\b', str(tag))
                       for spell in spells()[0] for tag in (spell.tags_json or []))
        if atom == 'capacidade de conjurar ao menos uma magia de teletransporte':
            return any(re.search(r'\bteleport\b', str(tag))
                       for spell in spells()[0] for tag in (spell.tags_json or []))
        cast = re.fullmatch(r'capacidade de conjurar (.+?)( a vontade)?', atom)
        if cast:
            name = re.sub(r'\s*\([^()]*\)', '', cast.group(1)).strip()
            return any(name in {views._prereq_label(spell.nome), views._prereq_label(spell.nome_ingles)}
                       and (not cast.group(2) or spell.slug in spells()[1]) for spell in spells()[0])
        return views._talento_prereq_ok(SimpleNamespace(pre_requisito=atom), person, ficha, context)

    def accepts(source, tier):
        text, _exclusions = views._talento_exclusoes_condicionais(source, lineages(source.id_raca_id))
        # Semicolons in older records have the same conjunction role as commas.
        clauses = [part.strip(' .') for part in re.split(r'[,;]', text) if part.strip(' .')]
        ficha = dict(sheet, nivel_total=tier)
        for clause in clauses:
            qualified = qualifier_clause(clause)
            if qualified is not None:
                if not qualified:
                    return False
                continue
            if not any(atom_ok(option, source, ficha) or (
                    ' e ' in option and all(atom_ok(part, source, ficha)
                                           for part in option.split(' e ')))
                    for option in re.split(r'\s+ou\s+', clause)):
                return False
        return True

    return accepts
