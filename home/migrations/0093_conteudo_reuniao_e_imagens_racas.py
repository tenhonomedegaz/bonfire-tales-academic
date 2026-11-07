import re

from django.db import migrations, models


CDN = (
    'https://wa-cdn.nyc3.digitaloceanspaces.com/user-data/production/'
    '672d154f-4c02-4530-b54f-b83d5894e1bc/uploads/images/'
)


RACE_IMAGES = {
    'anao': '32dfb438d66cdc145bddc3189102019b.png',
    'elfo': '7c127a2cd9fcfd8275c6ad1d13a67738.png',
    'humano': '8565797e064b3b1c43d9f24e5f455d55.png',
    'orc': '50071435da37cb00f36416e0b6eb11cd.png',
}

LINEAGE_IMAGES = {
    'montanha': '32dfb438d66cdc145bddc3189102019b.png',
    'profundezas': 'ef8154a8aa4629706f5246f2f3343dab.png',
    'aetherin': '7c127a2cd9fcfd8275c6ad1d13a67738.png',
    'sylvanar': 'a0b3b1fde94069a55c4c657d300dcb40.png',
    'noctelar': '2b44b9df52b94743ff9b3ba9153c6ffd.png',
    'lunareth': 'ba9673c3ba88e761bfdaff22b437e96a.png',
    'solariin': '262987d7645fc854ae45b4a613091555.png',
    'erthari': '8565797e064b3b1c43d9f24e5f455d55.png',
    'sálarin': '1427c3ed06cb88f9767b8bcc5ff34b18.png',
    'durkarn': 'ecb1c44b75c7e83b0319b88f63918900.png',
    'goruun': '2860a27640abb1ee5292a124edacffef.png',
    'verde': '50071435da37cb00f36416e0b6eb11cd.png',
    'negro': '34066164b51211272589aeca01f2eb4b.jpeg',
    'vermelho': 'c42e84e8f3e07d7bf60047f24e61774c.png',
    'cinza': '00e796ad66539fe17e9d140936be81dc.png',
    'branco': '236af24aa3b31116c1796a75846d7f1d.png',
}

ESSENCE_IMAGES = {
    'draconica': 'f95efdf11931da207873db8f6f91bcc9.png',
    'elemental': '8b37461df0fc06be9030079d5fc03115.png',
    'nephilim': '96c63b0fea80ceeb9894b4e2953dc4b8.png',
    'vampirismo': '1d558b9aa8d1b5ebbc1088cad89931d1.jpeg',
}


STARTING_EQUIPMENT = {
    'artifice': (
        'starting_equipment{'
        'item{slug:studded-leather-armor, qty:1}, item{slug:arma-adaga, qty:1}, '
        'item{slug:ferr-ferramentas-de-ladrao, qty:1}, '
        'item{slug:ferr-ferramentas-de-funileiro, qty:1}, '
        'item{slug:dungeoneer-s-pack, qty:1}, currency{po:16}, '
        'alternative{currency{po:150}}}'
    ),
    'barbaro': (
        'starting_equipment{item{slug:hide-armor, qty:1}, '
        'item{slug:arma-machado-grande, qty:1}, item{slug:arma-machadinha, qty:4}, '
        'item{slug:explorer-s-pack, qty:1}, currency{po:80}, '
        'alternative{currency{po:150}}}'
    ),
    'bardo': (
        'starting_equipment{item{slug:leather-armor, qty:1}, '
        'item{slug:arma-rapieira, qty:1}, item{slug:ferr-alaude, qty:1}, '
        'item{slug:arma-adaga, qty:1}, item{slug:entertainer-s-pack, qty:1}, '
        'currency{po:38}, alternative{currency{po:150}}}'
    ),
    'cacador': (
        'starting_equipment{item{slug:studded-leather-armor, qty:1}, '
        'item{slug:arma-cimitarra, qty:1}, item{slug:arma-espada-curta, qty:1}, '
        'item{slug:arma-arco-longo, qty:1}, item{slug:arrows-20, qty:1}, '
        'item{slug:quiver, qty:1}, item{slug:sprig-of-mistletoe, qty:1}, '
        'item{slug:explorer-s-pack, qty:1}, currency{po:7}, '
        'alternative{currency{po:150}}}'
    ),
    'clerigo': (
        'starting_equipment{item{slug:chain-mail, qty:1}, item{slug:shield, qty:1}, '
        'item{slug:arma-maca, qty:1}, item{slug:holy-symbol, qty:1}, '
        'item{slug:priest-s-pack, qty:1}, currency{po:22}, '
        'alternative{currency{po:150}}}'
    ),
    'druida': (
        'starting_equipment{item{slug:studded-leather-armor, qty:1}, '
        'item{slug:shield, qty:1}, item{slug:arma-cimitarra, qty:1}, '
        'item{slug:druidic-focus, qty:1}, item{slug:explorer-s-pack, qty:1}, '
        'item{slug:ferr-kit-de-herborismo, qty:1}, currency{po:40}, '
        'alternative{currency{po:150}}}'
    ),
    'feiticeiro': (
        'starting_equipment{item{slug:arma-besta-leve, qty:1}, '
        'item{slug:bolts-20, qty:1}, item{slug:arma-adaga, qty:2}, '
        'item{slug:crystal, qty:1}, item{slug:explorer-s-pack, qty:1}, '
        'currency{po:102}, alternative{currency{po:150}}}'
    ),
    'guerreiro': (
        'starting_equipment{item{slug:chain-mail, qty:1}, item{slug:shield, qty:1}, '
        'item{slug:arma-espada-longa, qty:1}, item{slug:arma-besta-leve, qty:1}, '
        'item{slug:bolts-20, qty:1}, item{slug:dungeoneer-s-pack, qty:1}, '
        'currency{po:12}, alternative{currency{po:150}}}'
    ),
    'ladino': (
        'starting_equipment{item{slug:studded-leather-armor, qty:1}, '
        'item{slug:arma-rapieira, qty:1}, item{slug:arma-arco-curto, qty:1}, '
        'item{slug:arrows-20, qty:1}, item{slug:arma-adaga, qty:2}, '
        'item{slug:ferr-ferramentas-de-ladrao, qty:1}, '
        'item{slug:burglar-s-pack, qty:1}, currency{po:9}, '
        'alternative{currency{po:150}}}'
    ),
    'mago': (
        'starting_equipment{item{slug:spellbook, qty:1}, item{slug:orb, qty:1}, '
        'item{slug:arma-adaga, qty:2}, item{slug:scholar-s-pack, qty:1}, '
        'item{slug:ink, qty:1}, item{slug:map-or-scroll-case, qty:1}, '
        'item{slug:robe, qty:1}, currency{po:24}, alternative{currency{po:150}}}'
    ),
    'mistico': (
        'starting_equipment{'
        'pick{count:1, option{key:kit_besta_leve, label:besta_leve_e_20_virotes, '
        'item{slug:arma-besta-leve, qty:1}, item{slug:bolts-20, qty:1}}, '
        'option{category:arma, subcategory_prefix:arma_simples, qty:1}}, '
        'pick{count:1, option{slug:component-pouch, qty:1}, '
        'option{slug:arcane-focus, qty:1}}, '
        'pick{count:1, option{slug:scholar-s-pack, qty:1}, '
        'option{slug:explorer-s-pack, qty:1}}, '
        'item{slug:leather-armor, qty:1}, '
        'pick{count:1, option{category:arma, subcategory_prefix:arma_simples, qty:1}}, '
        'item{slug:arma-adaga, qty:2}, alternative{currency{po:150}}}'
    ),
    'monge': (
        'starting_equipment{item{slug:arma-lanca, qty:1}, '
        'item{slug:arma-adaga, qty:5}, '
        'pick{count:1, option{category:ferramenta, subcategory:ferramenta_artesao, qty:1}}, '
        'item{slug:explorer-s-pack, qty:1}, currency{po:130}, '
        'alternative{currency{po:150}}}'
    ),
    'paladino': (
        'starting_equipment{item{slug:chain-mail, qty:1}, item{slug:shield, qty:1}, '
        'item{slug:arma-espada-longa, qty:1}, item{slug:holy-symbol, qty:1}, '
        'item{slug:priest-s-pack, qty:1}, currency{po:12}, '
        'alternative{currency{po:150}}}'
    ),
}


TAG_MODELS = (
    'TbClasse', 'TbClassehabilidade', 'TbOpcaojogo', 'TbAntecedente',
    'TbEssencia', 'TbTracoracial', 'TbTalento', 'TbItemMundano',
    'TbItemMagico', 'TbMagia', 'TbBestiario',
)


NON_CONDITIONS = (
    'afastado', 'banido', 'debilitante', 'doente', 'enlarge', 'frenesi',
    'frenesi-de-sangue', 'golpe-fantasmagorico', 'in-receptaculo',
    'incorporeo', 'marca-guardiao', 'mutagenico', 'possuido',
    'queimando', 'restricao-de-acao', 'seduzido', 'vibracoes-letais',
)


def _remove_asi_benefit_lines(text):
    lines = []
    for line in (text or '').splitlines():
        if re.match(
            r'^\s*[-*]\s*\*\*\[?Aumento de Atributo\]?(?:\([^)]*\))?\*\*\s*:',
            line,
            flags=re.I,
        ):
            continue
        lines.append(line)
    return '\n'.join(lines)


def _rule_refs(text):
    return re.sub(
        r'\[Aumento de Atributo\]\([^)]*\)',
        '[Aumento de Atributo](tbRegra, aumento-de-atributo)',
        text or '',
        flags=re.I,
    )


def _normalize_upcast(value, cantrip=False):
    if isinstance(value, list):
        return [_normalize_upcast(item, cantrip=cantrip) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_upcast(item, cantrip=cantrip) for key, item in value.items()}
    if not isinstance(value, str) or 'upcast:' not in value:
        return value

    def replace(match):
        body = re.sub(r'/\s*nivel\b', '', match.group(1))
        body = body.strip()
        if cantrip:
            return (
                'scaling{by:character_level, at{5:%s, 11:%s, 17:%s}}'
                % (body, body, body)
            )
        return 'upcast{per:slot_level_above_base, %s}' % body

    value = re.sub(r'upcast\s*:\s*\{([^{}]*/\s*nivel[^{}]*)\}', replace, value)
    value = re.sub(
        r'upcast\s*:\s*\{([^{}]*/\s*carga[^{}]*)\}',
        lambda match: 'scaling{per:charge_spent, %s}' % re.sub(
            r'/\s*carga\b', '', match.group(1)).strip(),
        value,
    )
    value = re.sub(
        r'upcast\s*:\s*\{(lvl\s*=)',
        r'scaling{by:character_level, \1',
        value,
    )
    value = value.replace(
        'upcast:{spell:sopro-do-dragao,',
        'scaling{by:character_level, spell:sopro-do-dragao,',
    )
    return value


def _normalize_effect_semantics(value):
    if isinstance(value, list):
        return [_normalize_effect_semantics(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_effect_semantics(item) for key, item in value.items()}
    if not isinstance(value, str):
        return value

    value = re.sub(r'\bcond_immune\s*:\s*doente\b', 'immune_effect:disease', value)
    value = re.sub(r'\bcond_immune\s*:\s*possuido\b', 'immune_effect:possession', value)
    value = re.sub(r'\bcondition\{possuido\b', 'effect{possession', value)
    value = re.sub(r'\bcleanse\s*:\s*doente\b', 'cleanse:effect{disease}', value)
    value = re.sub(r'(?<=[{| ])doente(?=\s*[|},])', 'effect{disease}', value)
    value = value.replace(
        'on_fail:apply:possuido(duration:until_reuse)',
        'on_fail:activate:defined{dominio_morto_vivo}'
        '(target:active, duration:until_reuse)',
    )
    value = value.replace(
        'apply:banido(target:hit, until:turn_end)',
        'banish{target:hit, duration:until_turn_end}',
    )
    value = value.replace(
        'apply:banido(duration:until_target_next_turn_end)',
        'banish{target:active, duration:until_target_next_turn_end}',
    )
    value = value.replace(
        'apply:queimando(target:objetos_inflamaveis, range:10ft(from:caster))',
        'ignites:flammable(target:objects, range:10ft(from:caster))',
    )
    value = value.replace(
        'on:already_possuido -> adv:save(against:possessor)',
        'if(effect{possession, target:active}):adv:save(against:source{possession})',
    )
    return value


def _remove_legacy_equipment_gold(value):
    """Remove a alternativa de 150 PO que foi atribuída ao antecedente.

    A alternativa pertence ao equipamento da classe. Mantê-la também em
    background_grants duplicava a mesma escolha na criação da ficha.
    """
    if isinstance(value, list):
        return [_remove_legacy_equipment_gold(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _remove_legacy_equipment_gold(item)
            for key, item in value.items()
        }
    if not isinstance(value, str):
        return value
    value = re.sub(
        r',\s*equip[_-](?:gold|ouro)[_-]alt\s*:\s*\d+', '', value,
        flags=re.I,
    )
    value = re.sub(
        r'equip[_-](?:gold|ouro)[_-]alt\s*:\s*\d+\s*,\s*', '', value,
        flags=re.I,
    )
    return value


def seed_content(apps, schema_editor):
    Raca = apps.get_model('home', 'TbRaca')
    Linhagem = apps.get_model('home', 'TbLinhagem')
    Essencia = apps.get_model('home', 'TbEssencia')
    Classe = apps.get_model('home', 'TbClasse')
    Habilidade = apps.get_model('home', 'TbClassehabilidade')
    Opcao = apps.get_model('home', 'TbOpcaojogo')
    Acesso = apps.get_model('home', 'TbAcessoopcao')
    Talento = apps.get_model('home', 'TbTalento')
    Regra = apps.get_model('home', 'TbRegra')
    Magia = apps.get_model('home', 'TbMagia')
    Condicao = apps.get_model('home', 'TbCondicao')
    ItemMundano = apps.get_model('home', 'TbItemMundano')
    PersonagemItem = apps.get_model('home', 'TbPersonagemItem')

    for slug, filename in RACE_IMAGES.items():
        Raca.objects.filter(slug=slug).update(imagem_url=CDN + filename)
    for slug, filename in LINEAGE_IMAGES.items():
        Linhagem.objects.filter(slug=slug).update(imagem_url=CDN + filename)
    for slug, filename in ESSENCE_IMAGES.items():
        Essencia.objects.filter(slug=slug).update(imagem_url=CDN + filename)

    Regra.objects.update_or_create(
        slug='aumento-de-atributo',
        defaults={
            'nome': 'Aumento de Atributo',
            'nome_en': 'Ability Score Improvement',
            'categoria': 'Progressão de personagem',
            'definicao': (
                'Quando uma característica concede um Aumento de Atributo, você distribui '
                '**2 pontos** entre seus atributos, aumentando um atributo em 2 ou dois '
                'atributos em 1, respeitando os limites da regra. Como alternativa, você '
                'pode escolher um **Talento Geral** para o qual cumpra os pré-requisitos; '
                'o aumento de atributo desse talento é aplicado pelos campos mecânicos dele.'
            ),
        },
    )

    for talent in Talento.objects.all().only('pk', 'descricao'):
        updated = _rule_refs(_remove_asi_benefit_lines(talent.descricao))
        if updated != (talent.descricao or ''):
            talent.descricao = updated
            talent.save(update_fields=['descricao'])

    for feature in Habilidade.objects.all().only('pk', 'descricao'):
        updated = _rule_refs(feature.descricao)
        if updated != (feature.descricao or ''):
            feature.descricao = updated
            feature.save(update_fields=['descricao'])

    replacements = {
        'Combatente Montado': ('[Evasão](tbClassehabilidade, ladino, evasao)', 'Evasão'),
        'Dom da Infusão Elemental': (
            '[reflexo instintivo](tbClassehabilidade, ordem-da-alianca-selvagem, reflexo-instintivo)',
            'reflexo instintivo',
        ),
        'Escudeiro do Amanhecer': (
            '[primeiro golpe](tbClassehabilidade, ladino, primeiro-golpe)',
            'primeiro golpe',
        ),
    }
    for name, (old, new) in replacements.items():
        talent = Talento.objects.filter(nome=name).first()
        if talent and old in (talent.descricao or ''):
            talent.descricao = talent.descricao.replace(old, new)
            talent.save(update_fields=['descricao'])

    fighter = Classe.objects.filter(slug='guerreiro').first()
    artificer = Classe.objects.filter(slug='artifice').first()
    if fighter:
        for option in Opcao.objects.filter(tipo='Estilo de Luta'):
            Acesso.objects.update_or_create(
                id_opcao=option,
                id_classe=fighter,
                id_subclasse=None,
                defaults={'nivel_recebimento': 1},
            )
    if artificer:
        for option in Opcao.objects.filter(tipo='Infusão'):
            Acesso.objects.update_or_create(
                id_opcao=option,
                id_classe=artificer,
                id_subclasse=None,
                defaults={'nivel_recebimento': 2},
            )

    martial = Talento.objects.filter(slug='adepto-marcial').first()
    if martial:
        tags = []
        for tag in (martial.tags_json or []):
            if str(tag).startswith('pick:opcao:estilo_de_luta:'):
                tag = 'pick:opcao:estilo_de_luta:1(from:classe{guerreiro}, reset:level_up)'
            tags.append(tag)
        martial.tags_json = tags
        martial.descricao = (martial.descricao or '').replace(
            '[Estilo de Luta](tbClassehabilidade, colegio-das-laminas, estilo-de-luta)',
            'Estilo de Luta',
        )
        if '::options=Estilo de Luta' not in martial.descricao:
            martial.descricao += (
                '\n\n::click Estilos de Luta do Guerreiro\n'
                '::options=Estilo de Luta; classe guerreiro\n::endclick'
            )
        martial.save(update_fields=['descricao', 'tags_json'])

    infusion = Habilidade.objects.filter(id_classe__slug='artifice', nome='Infusões').first()
    if infusion:
        infusion.descricao = (infusion.descricao or '').replace(
            '::options=Infusões do Artífice',
            '::options=Infusão; classe artifice; nivel 20',
        ).replace(')./li]', ').')
        infusion.save(update_fields=['descricao'])

    for slug, equipment_tag in STARTING_EQUIPMENT.items():
        classe = Classe.objects.filter(slug=slug).first()
        if not classe:
            continue
        tags = [tag for tag in (classe.tags_json or [])
                if not str(tag).strip().startswith('starting_equipment{')]
        tags.append(equipment_tag)
        classe.tags_json = tags
        classe.save(update_fields=['tags_json'])

    command_undead = Habilidade.objects.filter(
        id_classe__slug='mago', nome='Comandar Mortos-Vivos').first()
    if command_undead:
        tags = list(command_undead.tags_json or [])
        if not any(str(tag).startswith('define{dominio_morto_vivo:') for tag in tags):
            tags.insert(0, 'define{dominio_morto_vivo: effect{control:target, source:self}}')
        command_undead.tags_json = tags
        command_undead.save(update_fields=['tags_json'])

    for model_name in TAG_MODELS:
        Model = apps.get_model('home', model_name)
        for obj in Model.objects.all().iterator():
            current = obj.tags_json or []
            updated = _remove_legacy_equipment_gold(current)
            updated = _normalize_effect_semantics(updated)
            updated = _normalize_upcast(
                updated,
                cantrip=(model_name == 'TbMagia' and int(getattr(obj, 'nivel', -1) or 0) == 0),
            )
            if updated != current:
                obj.tags_json = updated
                obj.save(update_fields=['tags_json'])

    Condicao.objects.filter(slug__in=NON_CONDITIONS).delete()

    # Liga posses antigas quando o nome identifica um único item do catálogo. Nomes
    # ambíguos permanecem apenas como snapshot, sem associação arbitrária.
    by_name = {}
    duplicates = set()
    for item in ItemMundano.objects.all().only('pk', 'nome'):
        key = (item.nome or '').strip().casefold()
        if key in by_name:
            duplicates.add(key)
        else:
            by_name[key] = item.pk
    for key in duplicates:
        by_name.pop(key, None)
    for possession in PersonagemItem.objects.filter(
            id_item_magico__isnull=True, id_item_mundano__isnull=True).only('pk', 'nome'):
        item_id = by_name.get((possession.nome or '').strip().casefold())
        if item_id:
            possession.id_item_mundano_id = item_id
            possession.save(update_fields=['id_item_mundano'])


def unseed_content(apps, schema_editor):
    Regra = apps.get_model('home', 'TbRegra')
    Regra.objects.filter(slug='aumento-de-atributo').delete()


class Migration(migrations.Migration):
    dependencies = [('home', '0092_tbconteudoestatico')]

    operations = [
        migrations.AddField(
            model_name='tbraca',
            name='imagem_url',
            field=models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tblinhagem',
            name='imagem_url',
            field=models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tbessencia',
            name='imagem_url',
            field=models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tbpersonagemitem',
            name='id_item_mundano',
            field=models.ForeignKey(
                blank=True, db_column='IdItemMundano', null=True,
                on_delete=models.SET_NULL, related_name='posses',
                to='home.tbitemmundano'),
        ),
        migrations.RunPython(seed_content, unseed_content),
    ]
