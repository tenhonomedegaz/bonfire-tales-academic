from django.db import migrations


BACKGROUND_REPLACEMENTS = {
    "Acólito": {
        "always_active{ check_attr:religiao:=wis, adv:check{religiao}(for:info_do_panteao) }":
            "always_active{ check_attr:religiao:=wis }",
    },
    "Antropologista": {
        "always_active{ adv:check{investigacao}(for:antropologia) }": None,
    },
    "Arqueologista": {
        "always_active{ adv:check{investigacao}(for:arqueologia) }": None,
    },
    "Artista": {
        "always_active{ adv:check{atuacao}(for:apresentar_em_estabelecimento) }": None,
        "while_active{ requires:apresentou_em_palco, target:creature(presente_na_apresentacao), adv:check{enganacao}, adv:check{persuasao} }": None,
    },
    "Assombrado": {
        "always_active{ adv:check{arcanismo}(for:espiritos_e_vida_apos_morte), adv:check{historia}(for:espiritos_e_vida_apos_morte), adv:check{religiao}(for:espiritos_e_vida_apos_morte) }": None,
    },
    "Astrônomo": {
        "always_active{ adv:check{investigacao}(for:{astrologia | astronomia | cosmologia}) }": None,
        "always_active{ recall:mapas_astrais_e_orientacao_noturna }": None,
    },
    "Campeão": {
        "always_active{ check_attr:atuacao:=str(for:performances_atleticas) }": None,
    },
    "Cavaleiro": {
        "always_active{ adv:check{persuasao}(for:conversar_com_cavaleiros) }": None,
    },
    "Charlatão": {
        "always_active{ adv:check{} (for:jogos_de_azar), adv:check{enganacao}(for:esconder_trapaca_em_jogo) }": None,
    },
    "Criminoso": {
        "always_active{ rede:contatos_criminais }": None,
    },
    "Detetive": {
        "always_active{ adv:check{}(for:obter_auxilio_de_autoridades) }": None,
        "while_active{ requires:investigando_cena_de_crime, adv:check{investigacao}, adv:check{percepcao} }": None,
        "always_active{ adv:check{intuicao}(for:detectar_mentira_em_caso_investigado) }": None,
    },
    "Espião": {
        "always_active{ rede:agentes_de_espionagem }": None,
    },
    "Estudante de Arcanofísica": {
        "always_active{ adv:check{}(for:raciocinio_logico_e_matematico) }": None,
    },
    "Estudante de Arqueomancia": {
        "always_active{ adv:check{}(for:datacao_de_ruinas_e_objetos) }": None,
    },
    "Estudante de Biomancia": {
        "always_active{ adv:check{}(for:organismos_e_doencas) }": None,
    },
    "Estudante de Estequiomancia": {
        "always_active{ adv:check{}(for:conhecimento_primordial_e_elemental) }": None,
    },
    "Estudante de Nanquinomancia": {
        "always_active{ adv:check{}(for:analisar_escrituras_magicas) }": None,
    },
    "Guardião da Natureza": {
        "always_active{ adv:check{adestrar_animais}(for:bestas_selvagens) }": None,
    },
    "Herói": {
        "always_active{ adv:check{persuasao}(for:{inspirar_ou_acalmar_plebeus | obter_info_de_arredores_de_vilarejos}) }": None,
    },
    "Legionário": {
        "action=action, instant{ requires:discurso(min:1min), target:allies, adv:check{persuasao}(for:coordenar_civis_em_emergencia) }": None,
    },
    "Marcado Pelas Fadas": {
        "always_active{ adv:check{intuicao}(for:conversa_com_feerico), adv:check{persuasao}(for:conversa_com_feerico) }": None,
    },
    "Mercenário": {
        "always_active{ rede:contratantes_mercenarios }": None,
        "always_active{ recall:contratos_e_eventos_locais }": None,
    },
    "Mestre Artesão": {
        "always_active{ prof:tool{pick:ferramenta_de_artesao:1}, adv:check{tool}(for:ferramenta_de_artesao_escolhida) }":
            "always_active{ prof:tool{pick:ferramenta_de_artesao:1} }",
        "always_active{ adv:check{}(for:negociar_com_mercadores) }": None,
    },
    "Nobre": {
        "always_active{ adv:check{persuasao}(for:conversar_com_nobres) }": None,
    },
    "Pescador": {
        "always_active{ adv:check{}(for:info_de_vida_maritima_e_ambientes_aquaticos) }": None,
        "always_active{ adv:check{}(for:usar_equipamento_de_pesca) }": None,
        "always_active{ adv:check{enganacao}(for:mentiras_sobre_vivencias_no_mar) }": None,
    },
    "Pesquisador": {
        "always_active{ adv:check{}(for:pesquisa_de_qualquer_estudo) }": None,
    },
    "Soldado": {
        "always_active{ patente:militar }": None,
    },
    "Viajante": {
        "always_active{ recall:terreno_e_geografia }": None,
    },
    "Viajante do Mar": {
        "always_active{ adv:check{persuasao}(for:pessoas_de_vida_maritima), adv:check{enganacao}(for:pessoas_de_vida_maritima) }": None,
    },
}

TRAIT_REPLACEMENTS = {
    "Caminhante da Neve": {
        "always_active{ no_difficult_terrain(source:{gelo | neve | escorregadio}) }":
            "always_active{ no_difficult_terrain(source:{gelo | neve | escorregadio}), adv:check{acrobacia}(terrain:{gelo | neve | escorregadio}) }",
    },
    "Natureza Morta-Viva": {
        "__append__": "always_active{ suppress:pick{talento_racial, source:raca} }",
    },
    "Visão de Predador": {
        "if(sense:darkvision): sense:darkvision(range:+30ft)":
            "sense:darkvision(range:+30ft, if_present)",
    },
    "Máscara da Comunidade": {
        "define{ mascara_comunidade: list{ sol_brilhante:{ prof:persuasao, cast{spell:orientacao, modifiers{no_slot}} }, mascara_da_morte:{ prof:natureza, adv:check{medicina}(for:estabilizar) }, corpo_consagrado:{ prof:religiao, check_attr:religiao:=sabedoria }, mao_vazia:{ prof:atletismo, unarmed_strike.dmg:=1d4+str_mod } } }":
            "define{ mascara_comunidade: list{ sol_brilhante:{ prof:persuasao, cast{spell:orientacao, modifiers{no_slot}} }, mascara_da_morte:{ prof:natureza, adv:check{medicina}(action:stabilize) }, corpo_consagrado:{ prof:religiao, check_attr:religiao:=sabedoria }, mao_vazia:{ prof:atletismo, unarmed_strike.dmg:=1d4+str_mod } } }",
    },
    "Corpo Superior": {
        "always_active{ move:climb(15ft), move:swim(15ft), adv:check{atletismo}(for:{saltar | escalar | nadar_em_aguas_turbulentas}) }":
            "always_active{ move:climb(15ft), move:swim(15ft), adv:check{atletismo}(action:{jump | climb}), adv:check{atletismo}(action:swim, terrain:turbulent_water) }",
    },
    "Segredos Sybaris": {
        "self.adv:next{attack or check{social} or charm}(against:target)":
            "self.adv:next{attack or charm}(against:target)",
    },
}


def _replace_tags(obj, replacements):
    tags = list(obj.tags_json or [])
    changed = False
    append_value = replacements.get("__append__")
    result = []
    for tag in tags:
        if tag not in replacements:
            result.append(tag)
            continue
        changed = True
        replacement = replacements[tag]
        if replacement:
            result.append(replacement)
    if append_value and append_value not in result:
        result.append(append_value)
        changed = True
    if changed:
        obj.tags_json = result
        obj.save(update_fields=["tags_json"])


def forwards(apps, schema_editor):
    Antecedente = apps.get_model("home", "TbAntecedente")
    Traco = apps.get_model("home", "TbTracoracial")
    for name, replacements in BACKGROUND_REPLACEMENTS.items():
        for obj in Antecedente.objects.filter(nome=name):
            _replace_tags(obj, replacements)
    for name, replacements in TRAIT_REPLACEMENTS.items():
        for obj in Traco.objects.filter(nome=name):
            _replace_tags(obj, replacements)


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0065_fix_ref_golpe_certeiro"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
