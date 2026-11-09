"""Origem e limites de magia do laboratório, usando os contratos da ficha."""
from .models import TbMagia, TbPersonagemMagia
from .spellcasting import acquired_spell_count, limit_at


def spell_sources(personagem, *, ruleset=None):
    from .views import (_caster_subclasse, _classe_spellcasting_info,
                        _class_max_spell_level, _spell_catalog_queryset)
    from .versioned_classes import resolved_classes

    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse'))
    if ruleset is not None:
        from types import SimpleNamespace
        from .models import TbClasse
        from .spell_access import access_key, spell_class_slugs
        from .spellcasting import character_spell_list_delta
        from .versioned_spells import spell_catalog, spell_scopes

        classes = resolved_classes(ruleset, classes)
        frozen_spells = spell_catalog(ruleset)
        scopes = spell_scopes(ruleset)
        frozen_classes = [SimpleNamespace(slug=slug, nome=scopes.get(slug.lower(), slug))
                          for slug in TbClasse.objects.values_list('slug', flat=True)]
        delta = character_spell_list_delta(personagem, ruleset=ruleset)

    sources = []
    for pc in classes:
        subclass = pc.id_subclasse if ruleset is not None else _caster_subclasse(pc)
        level = int(pc.nivel or 1)
        info = _classe_spellcasting_info(pc.id_classe, level, subclass, ruleset=ruleset)
        if not info:
            continue
        maximum = _class_max_spell_level(pc.id_classe, level, info, subclass,
                                         ruleset=ruleset)
        if ruleset is None:
            allowed = set(_spell_catalog_queryset(info['lista_nomes'], personagem)
                          .filter(nivel__lte=maximum).values_list('id_magia', flat=True))
        else:
            wanted = {row.slug for row in frozen_classes
                      if access_key(row.nome) in {access_key(name) for name in info['lista_nomes']}}
            allowed = {spell.pk for spell in frozen_spells.values()
                       if int(spell.nivel or 0) <= maximum
                       and spell.slug not in delta['remove']
                       and (spell.slug in delta['add'] or
                            wanted.intersection(spell_class_slugs(
                                spell, classes=frozen_classes)))}
        sources.append({'pc': pc, 'subclass': subclass, 'info': info,
                        'allowed': allowed, 'maximum': maximum})
    return sources


def apply_spell_selection(personagem, build, *, ruleset=None):
    """Aplica somente na transação de simulação; ambiguidades ficam diagnosticáveis."""
    rows = build.get('magias', [])
    if not isinstance(rows, list) or len(rows) > 580:
        raise ValueError('Lista de magias invalida.')
    if any(not isinstance(row, dict) or not isinstance(row.get('slug'), str) or
           not row['slug'] or
           (row.get('classe') is not None and not isinstance(row['classe'], str)) or
           ('preparada' in row and type(row['preparada']) is not bool)
           for row in rows):
        raise ValueError('Selecao de magia invalida.')
    slugs = {str(row.get('slug') or '') for row in rows}
    spells = {m.slug: m for m in TbMagia.objects.filter(slug__in=slugs)}
    if slugs != set(spells):
        raise ValueError('Uma das magias selecionadas nao existe.')
    if ruleset is not None:
        from .versioned_spells import spell_catalog
        frozen = {spell.slug: spell for spell in spell_catalog(ruleset).values()}
        if not slugs <= set(frozen):
            raise ValueError('Uma das magias selecionadas nao pertence a revisao.')
    sources = spell_sources(personagem, ruleset=ruleset)
    personagem._pathbuilder_base_spells = {
        (m.id_magia_id, m.origem): m.preparada
        for m in personagem.magias.filter(sempre_preparada=False)
    }
    by_slug = {s['pc'].id_classe.slug: s for s in sources}
    issues, seen = [], set()
    for row in rows:
        spell = spells[str(row.get('slug') or '')]
        shown_spell = frozen[spell.slug] if ruleset is not None else spell
        source_slug = str(row.get('classe') or '')
        source = by_slug.get(source_slug)
        if not source_slug:
            owned = [s for s in sources if personagem.magias.filter(
                id_magia=spell, origem=s['pc'].id_classe.nome,
                sempre_preparada=False).exists()]
            candidates = owned or [s for s in sources if spell.pk in s['allowed']]
            if len(candidates) == 1:
                source = candidates[0]
            elif len(candidates) > 1:
                issues.append('Escolha a classe de origem de %s; há mais de uma fonte elegível.' % shown_spell.nome)
        if source:
            origin = source['pc'].id_classe.nome
        else:
            origin = 'Pathbuilder'
            if source_slug:
                issues.append('A origem %s de %s não é uma classe conjuradora desta build.'
                              % (source_slug, shown_spell.nome))
            elif not any(shown_spell.nome in issue for issue in issues):
                issues.append('Magia %s (círculo %d) sem classe elegível nesta progressão.'
                              % (shown_spell.nome, shown_spell.nivel or 0))
        key = (spell.pk, origin)
        if key in seen:
            raise ValueError('Magia repetida para a mesma origem: %s.' % shown_spell.nome)
        seen.add(key)
        # Uma concessão inata não substitui o repertório de classe, nem é editada por ele.
        current = personagem.magias.filter(id_magia=spell, origem=origin,
                                            sempre_preparada=False).first()
        prepared = row.get('preparada', True)
        if current:
            current.preparada = prepared
            current.save(update_fields=['preparada'])
        else:
            TbPersonagemMagia.objects.create(id_personagem=personagem, id_magia=spell,
                nivel=shown_spell.nivel, nome=shown_spell.nome, preparada=prepared, origem=origin)
    personagem._pathbuilder_staged_spell_keys = seen
    personagem._pathbuilder_spell_issues = issues


def spell_review(personagem, ficha, *, ruleset=None):
    """Conta repertório por classe; slots de multiclasse não liberam círculos adicionais."""
    from .views import _ABIL_EN

    issues = list(getattr(personagem, '_pathbuilder_spell_issues', []))
    context = {'lvl': ficha['nivel_total'], 'pb': ficha['bonus_proficiencia']}
    context.update({en + '_mod': ficha['atributos'][sig]['mod'] for sig, en in _ABIL_EN.items()})
    public = []
    baseline = getattr(personagem, '_pathbuilder_base_spells', {})
    for source in spell_sources(personagem, ruleset=ruleset):
        pc, info = source['pc'], source['info']
        classe, level = pc.id_classe, int(pc.nivel or 1)
        rows = list(personagem.magias.filter(origem=classe.nome, sempre_preparada=False)
                    .select_related('id_magia'))
        unique = {m.id_magia_id: m for m in rows if m.id_magia_id}
        for row in unique.values():
            if row.id_magia_id not in source['allowed']:
                issues.append('Magia %s (círculo %d) fora da lista ou círculo de %s %d.'
                              % (row.nome, row.nivel or 0, classe.nome, level))
        ctx = dict(context, classlvl=level)
        abilities = str(info.get('ability') or '').split('|')
        ctx['spell_mod'] = max((ctx.get(a + '_mod', 0) for a in abilities), default=0)

        def resolve(spec):
            value = limit_at(spec, classe, level=level, context=ctx,
                            subclass=source['subclass'],
                            minimum=1 if (spec or {}).get('kind') == 'formula' else 0,
                            ruleset=ruleset)
            if spec and value is None:
                issues.append('%s %d: limite de magia indisponível; revise o contrato de conteúdo.'
                              % (classe.nome, level))
            return value

        def exact(label, used, expected):
            if expected is not None and used != expected:
                issues.append('%s %d: %s %d/%d; %s %d.' % (
                    classe.nome, level, label, used, expected,
                    'selecione mais' if used < expected else 'remova', abs(expected - used)))

        cantrips = sum(int(m.nivel or 0) == 0 for m in unique.values())
        spells = sum(int(m.nivel or 0) > 0 for m in unique.values())
        prepared = sum(int(m.nivel or 0) > 0 and m.preparada for m in unique.values())
        cantrip_limit = resolve(info.get('cantrip_limit')) if info.get('cantrip_limit') else 0
        spell_limit = resolve(info.get('spell_limit'))
        exact('truques', cantrips, cantrip_limit)
        if info.get('mode') == 'known':
            exact('magias conhecidas', spells, spell_limit)
        elif info.get('mode') == 'prepared' and spell_limit is not None and prepared > spell_limit:
            issues.append('%s %d: magias preparadas %d/%d; desmarque %d.' % (
                classe.nome, level, prepared, spell_limit, prepared - spell_limit))
        minimum = acquired_spell_count(info, level=level) if info.get('pool') == 'spellbook' else 0
        if spells < minimum:
            issues.append('%s %d: grimório %d/%d; selecione mais %d magia(s).' % (
                classe.nome, level, spells, minimum, minimum - spells))
        public.append({'slug': classe.slug, 'nome': classe.nome, 'nivel': level,
            'mode': info.get('mode'), 'pool': info.get('pool'),
            'truques': cantrips, 'limite_truques': cantrip_limit,
            'conhecidas': spells, 'preparadas': prepared, 'limite_magias': spell_limit,
            'minimo_grimorio': minimum,
            'magias': [{'slug': m.id_magia.slug, 'nome': m.nome, 'nivel': m.nivel,
                        'preparada': m.preparada, 'sempre_preparada': m.sempre_preparada,
                        'base': (m.id_magia_id, m.origem) in baseline,
                        'preparada_base': baseline.get((m.id_magia_id, m.origem), False)}
                       for m in unique.values()]})
    return issues, public
