# -*- coding: utf-8 -*-
"""Dados mecanicos do rework do Bardo publicado em 2026-07-24.

O HTML e a fonte da descricao. Este modulo guarda apenas a camada executavel
que nao pode ser inferida com seguranca do texto livre.
"""

CLASS_TAGS = [
    "hit_dice:1d8",
    "saves_prof{dex, cha}",
    "skills_lvl1{pick:3}",
    "subclass_choices{3, 6, 14, 18}",
    "asi_choices{4, 8, 12, 16, 19}",
    "multiclass_req{cha>=13}",
    "multiclass_prof{armadura_leve, pick:ferramenta:instrumento:1}",
    "prof{armadura_leve, armas_simples}",
    "prof{pick:ferramenta:instrumento:3}",
]

CLASS_METADATA = {
    "atributo_principal": "Carisma",
    "dado_vida": "1d8 por nível de Bardo",
    "pv_nivel_1": "8 + seu modificador de Constituição",
    "pv_por_nivel": "1d8 (ou 5) + seu modificador de Constituição",
    "resistencias": "Destreza, Carisma",
    "pericias": "Escolha 3 quaisquer",
    "armas": "Armas Simples",
    "ferramentas": (
        "Três Instrumentos Musicais à sua escolha (ou focos artísticos "
        "equivalentes, conforme a sua arte)"
    ),
    "armaduras": "Armadura Leve",
    "equipamento": (
        "(A) Armadura de Couro, Rapieira, Alaúde como foco da sua arte, "
        "Adaga, Pacote do Animador e 38 PO; ou (B) 150 PO."
    ),
    "multiclass_requisitos": "Carisma 13",
    "multiclass_pericias": "",
    "multiclass_armas": "",
    "multiclass_ferramentas": "Um Instrumento Musical à sua escolha",
    "multiclass_armaduras": "Armadura Leve",
}

BASE_TAGS = {
    "Conjuração": [
        "spellcasting{ability:cha, slots:full, lista:bardo, prepara:conhecidas, foco:instrumento_musical}",
        "define{cd:8+pb+cha_mod, spell_attack:pb+cha_mod}",
        "swap:level_up",
    ],
    "Inspiração Bárdica": [
        "resource{dado_de_inspiracao}",
        "define{inspiracao_bardica:max:max(cha_mod,1), reset:long_rest}",
        "action=bonus_action",
        (
            "instant{resource_cost:inspiracao_bardica:1, "
            "grant:resource{dado_de_inspiracao}:1"
            "(target:creature(range:60ft, see_or_hear), "
            "max:1/creature, duration:60min)}"
        ),
        (
            "define{dado_de_inspiracao:on:fail{ability_check, attack, save} "
            "-> roll_add:+roll{resource:dado_de_inspiracao}}"
        ),
    ],
    "Acordes de Poder": [
        (
            "always_active{pick:opcao:acordes_de_poder:"
            "{classlvl=2:2, classlvl=4:+1, classlvl=6:+1, "
            "classlvl=10:+1, classlvl=14:+1, classlvl=18:+1}"
            "(swap:level_up)}"
        ),
        (
            "define{apresentacao:action:magic_action, "
            "resource_cost:inspiracao_bardica:1, "
            "check:cha(atuacao), "
            "cd:match(grau){1:15,2:20,3:25,4:30}, "
            "resultado:{success:maior, fail:menor}, "
            "duration:until_next_turn, sustain:bonus_action, "
            "concentration, aura:30ft(self), "
            "enemy_requires:{see,hear}, once_per_turn}"
        ),
        (
            "restriction{requires:concentrating_on_spell}"
            "(until:ability{virtuose_da_apresentacao, classe:bardo})"
        ),
    ],
    "Especialização": [
        (
            "always_active{pick:pericia_expertise:"
            "{classlvl=2:2, classlvl=9:+2}(requires:proficient)}"
        )
    ],
    "Pau Pra Toda Obra": [
        "always_active{ability_check:+rounddown(pb/2)(unless:proficient)}"
    ],
    "Colégio de Bardo": [],
    "Aprimoramento de Atributo ou Talento": [],
    "Fonte de Inspiração": [
        (
            "always_active{modify:resource{inspiracao_bardica}."
            "reset:={short_rest, long_rest}}"
        ),
        (
            "action=free, instant{resource_cost:spell_slot:1 "
            "-> resource_restore:inspiracao_bardica:1}"
        ),
    ],
    "Contra-Canto": [
        "action=reaction",
        (
            "trigger=fail_save(target:self+creature(range:30ft), "
            "vs:{enfeiticado, amedrontado})"
        ),
        "instant{reroll:save(adv, same_cd)}",
    ],
    "Segredos Mágicos": [
        (
            "spell_selection:lista:[bardo, clerigo, druida, mago]"
            "{efeito:known_spell, ability:cha}"
        ),
        "swap:level_up",
    ],
    "Virtuose da Apresentação": [
        (
            "always_active{allow_concentration:2"
            "(requires:one_spell_and_one_presentation, "
            "lose_together:true)}"
        )
    ],
    "Inspiração Superior": [
        "trigger=initiative",
        (
            "instant{if(resource{inspiracao_bardica}<2):"
            "resource{inspiracao_bardica}:=2}"
        ),
    ],
    "Palavras da Criação": [
        (
            "spell_selection:list{palavra_de_poder_cura, "
            "palavra_de_poder_matar}{efeito:known_spell(extra), ability:cha}"
        ),
        (
            "cast{spell:palavra-de-poder-cura, "
            "modifiers{targets:+1(range:10ft)}}"
        ),
        (
            "cast{spell:palavra-de-poder-matar, "
            "modifiers{targets:+1(range:10ft)}}"
        ),
    ],
}

SUBCLASS_TAGS = {
    ("colegio-do-conselho", "Conselho Bárdico"): [
        (
            "always_active{prof:enganacao, prof:historia, prof:persuasao, "
            "trigger=ability_check{enganacao,persuasao}, "
            "requires:roll{dice:1d20}<=9, instant{replace_d20:10}, "
            "requires:!ability{acordes_de_poder, classe:bardo}}"
        )
    ],
    ("colegio-do-conselho", "Lógica Cortante"): [
        (
            "while_active{action:reaction, "
            "trigger=creature_roll{attack_roll,save,ability_check,"
            "range:60ft,hear_and_understand}, "
            "instant{resource_cost:inspiracao_bardica:1, "
            "pick:modifier:1(from:[add,subtract]), "
            "roll_add:modifier*roll{resource:dado_de_inspiracao}}}"
        )
    ],
    ("colegio-do-conselho", "Língua Ancestral"): [
        (
            "while_active{action:action, "
            "instant{aura{radius:60ft,target:all,"
            "effects{requires:{hear_you,speaks_language},"
            "define{understands_as_native}},duration:hours:1},"
            "resource_cost:{1/long_rest|spell_slot{nivel>=2}}}}"
        )
    ],
    ("colegio-do-conselho", "Conselho Potente"): [
        (
            "while_active{trigger=ability{logica_cortante, classe:bardo}, "
            "on:target_miss_or_fail -> "
            "instant{resource_restore:inspiracao_bardica:1}}"
        )
    ],
    ("colegio-do-conselho", "Oratória Arrebatadora"): [
        (
            "while_active{trigger=ability{acordes_de_poder, classe:bardo}."
            "{start,sustain}, instant{grant:roll_add:+1d4"
            "(target:ally(in:presentation_aura), "
            "next:d20, duration:until_next_turn)}}"
        )
    ],
    ("colegio-do-conselho", "Perícia Inigualável"): [
        (
            "while_active{trigger=fail_check, "
            "instant{resource_cost:inspiracao_bardica:1, "
            "roll_add:+roll{resource:dado_de_inspiracao}}, "
            "on:fail_again -> "
            "instant{resource_restore:inspiracao_bardica:1}}"
        )
    ],
    ("colegio-do-conselho", "Palavras Contagiantes"): [
        (
            "while_active{action:free, "
            "trigger=ally_success_with_inspiration(range:60ft), "
            "trigger=enemy_fail_from{ability{logica_cortante, classe:bardo}}, "
            "instant{grant:resource{dado_de_inspiracao}:1"
            "@ally(range:60ft,hear_you)}, "
            "uses{max(cha_mod,1),reset:long_rest}}"
        )
    ],
    ("colegio-da-conspiracao", "Influência Astuta"): [
        (
            "always_active{prof:enganacao, "
            "pick:ferramenta:2 de [kit_de_disfarces,kit_de_falsificacao,"
            "kit_de_venenos,ferramentas_de_ladrao]}"
        ),
        (
            "while_active{trigger=cast{spell:pick{lista:bardo},"
            "componente:verbal,targets:1,range<=10ft},"
            "instant{define{only_target_hears_verbal}}}"
        ),
    ],
    ("colegio-da-conspiracao", "Assalto Psíquico"): [
        (
            "while_active{trigger=hit_attack,requires:weapon,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "dmg:+roll{resource:dado_de_inspiracao,"
            "dice:match(classlvl){classlvl<6:2,classlvl<14:3,"
            "classlvl<18:4,default:5}}(psiquico)}}"
        )
    ],
    ("colegio-da-conspiracao", "Sementes do Terror"): [
        (
            "while_active{requires:talk_1_minute,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{wis,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{apply:amedrontado(target:chosen_creature,"
            "duration:hours:1),define{treats_as_enemy}},"
            "define{ends_on:ally_attack,target_unaware}}}"
        )
    ],
    ("colegio-da-conspiracao", "Visagem Roubada"): [
        (
            "while_active{action:reaction,"
            "trigger=creature_dies{tipo:humanoide,see,range:30ft},"
            "instant{define{captured_visage}},"
            "action:action,instant{define{consume_visage:"
            "transform:captured_humanoid(duration:hours:1,"
            "opposed_check:insight_vs_deception)}},"
            "define{max_visages:1}}"
        )
    ],
    ("colegio-da-conspiracao", "Encenação Velada"): [
        (
            "while_active{trigger=ability{acordes_de_poder, classe:bardo}."
            "{start,sustain}, instant{grant:roll_add:-1d4"
            "(target:creature(in:presentation_aura),next:d20,"
            "duration:until_next_turn)}, "
            "define{major_origin_hidden:"
            "unless:insight_or_investigation>=presentation_cd}}"
        )
    ],
    ("colegio-da-conspiracao", "Manipulação Sinistra"): [
        (
            "while_active{action:action,"
            "modify:ability{sementes_do_terror, classe:bardo}."
            "on_fail:={apply:enfeiticado(duration:indefinite,"
            "save_again:each_turn_in_imminent_danger,"
            "ends_on:hostility),define{secretly_helps}},"
            "define{max_charmed:1}}"
        )
    ],
    ("colegio-da-conspiracao", "Angústia Mental"): [
        (
            "while_active{trigger=ability{assalto_psiquico, classe:bardo},"
            "instant{save{wis,dadv,"
            "cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:apply:amedrontado(duration:until_next_turn_end)}}"
        ),
        (
            "while_active{trigger=hit_attack,"
            "requires:{weapon,target{amedrontado_de_voce}},"
            "instant{cleanse:amedrontado@target,crit}}"
        ),
    ],
    ("colegio-da-criacao", "Instrumentos do Artesão"): [
        "always_active{pick:ferramenta:3}"
    ],
    ("colegio-da-criacao", "Fragmento da Canção"): [
        (
            "while_active{trigger=grant_inspiration,"
            "instant{define{fragmento:marca_orbital(range:5ft,"
            "duration:until_spend_inspiration)}},"
            "on:spend_inspiration -> match(roll_context){"
            "ability_check:{roll{dice:resource{dado_de_inspiracao}x2,"
            "keep:highest}},attack_roll:{aoe{point:target,radius:5ft,"
            "save{con,cd=ability{conjuracao, classe:bardo}.cd},"
            "dmg:roll{resource:dado_de_inspiracao}(trovejante),"
            "on_success:none}},saving_throw:{temp_hp:+"
            "(roll{resource:dado_de_inspiracao}+max(cha_mod,1))@target}}}"
        )
    ],
    ("colegio-da-criacao", "Obra da Criação"): [
        (
            "while_active{action:action,"
            "instant{define{obra:object(nonmagical,visible_magic,"
            "size<=large,range:10ft,hp:classlvl,ca:cha_score,"
            "duration:hours:1,value_max:20*classlvl,"
            "requires:{familiar,tool_proficiency},"
            "can_replace:material_component)}},"
            "resource_cost:{1/long_rest|spell_slot{nivel>=2}},"
            "define{max_active:1}}"
        )
    ],
    ("colegio-da-criacao", "Dança da Criação"): [
        (
            "while_active{action:action,"
            "instant{summon:define{item_dancante(range:30ft,size<=large,"
            "ca:14+pb,hp:10+5*classlvl,speed:30ft,"
            "movement:[walk,hover],attack_dice:"
            "match(classlvl){classlvl<11:1d8,classlvl<17:2d8,"
            "default:3d8},damage:energia,uses_pb:true)}},"
            "resource_cost:{1/long_rest|spell_slot{nivel>=3}},"
            "define{max_active:1}}"
        )
    ],
    ("colegio-da-criacao", "Acordes em Coro"): [
        (
            "while_active{modify:ability{acordes_de_poder, classe:bardo}."
            "max_active:=2,define{cost_per_accord:"
            "resource_cost:inspiracao_bardica:1},"
            "action:bonus_action,"
            "instant{sustain:presentation,command:item_dancante}}"
        )
    ],
    ("colegio-da-criacao", "Crescendo Criativo"): [
        (
            "while_active{modify:ability{obra_da_criacao, classe:bardo}."
            "max_active:=max(cha_mod,2),"
            "define{only_one_max_size,others:[small,tiny],"
            "total_value_max:50*classlvl,cannot_sell},"
            "modify:ability{obra_da_criacao, classe:bardo}."
            "with_spell_slot.duration:=hours:24}"
        )
    ],
    ("colegio-da-criacao", "Canção Verdadeira"): [
        (
            "while_active{modify:ability{obra_da_criacao, classe:bardo}."
            "with_spell_slot.duration:=permanent}"
        ),
        (
            "while_active{modify:ability{danca_da_criacao, classe:bardo}."
            "max_active:=2,define{second_item:"
            "resource_cost:spell_slot{nivel>=3},command_both:same_action}}"
        ),
        (
            "while_active{1/turn,"
            "trigger=cast{spell:pick{lista:bardo}},"
            "trigger=grant_inspiration,"
            "instant{grant:extra_action(help)@item_dancante}}"
        ),
        (
            "spell_selection:any{spell:despertar,"
            "always_prepared,extra,fora_do_limite}"
        ),
        (
            "cast{spell:despertar,modifiers{without{material}},"
            "uses{1,reset:long_rest}}"
        ),
    ],
    ("colegio-da-danca", "Corpo em Cena"): [
        (
            "always_active{prof:atuacao,if(prof:atuacao):expertise:atuacao,"
            "trigger=performance_check{dance},"
            "requires:roll{dice:1d20}<=9,instant{replace_d20:10},"
            "requires:!ability{acordes_de_poder, classe:bardo}}"
        )
    ],
    ("colegio-da-danca", "Graça do Bailarino"): [
        (
            "always_active{restriction{equiped{armor,shield}},"
            "ca=10+dex_mod+cha_mod}"
        ),
        (
            "while_active{action:bonus_action,"
            "instant{pick:action:1(from:[dash,disengage])}}"
        ),
    ],
    ("colegio-da-danca", "Bailados de Combate"): [
        (
            "always_active{pick:opcao:bailados_de_combate:"
            "{classlvl=3:2,classlvl=6:+1,classlvl=14:+1,classlvl=18:+1}"
            "(swap:level_up),unarmed_strike.attr:=dex,"
            "trigger=use_bailado,"
            "instant{unarmed_strike.attr:=cha(duration:until_next_turn_end)}}"
        )
    ],
    ("colegio-da-danca", "Inspiração em Movimento"): [
        (
            "while_active{trigger=ally_use_inspiration,"
            "instant{move:15ft@target(without{opportunity_attack})}}"
        )
    ],
    ("colegio-da-danca", "Abertura de Palco"): [
        (
            "while_active{action:bonus_action,"
            "action:reaction(trigger:initiative),"
            "instant{resource_cost:inspiracao_bardica:1,"
            "while_active{duration:minutes:1,"
            "restriction{incapacitado},"
            "requires:move>=5ft_per_turn,"
            "move:without{opportunity_attack},adv:dex_save,"
            "trigger=use_bailado -> "
            "grant:resource{dado_de_inspiracao}:1"
            "@ally(range:60ft,see_or_hear),"
            "trigger=move>=half_speed -> "
            "sustain:ability{acordes_de_poder, classe:bardo}(without{action})}}}"
        )
    ],
    ("colegio-da-danca", "Conjuração em Movimento"): [
        (
            "while_active{trigger=cast{spell:pick{lista:bardo},"
            "componente:verbal},requires:move>=5ft,"
            "instant{modify:spell_component{verbal}:=dance,"
            "define{works_while_silenced}}}"
        )
    ],
    ("colegio-da-danca", "Evasão Coreografada"): [
        (
            "while_active{restriction{incapacitado},"
            "source{aoe}.save{dex}.on_success:=none,on_fail:=half,"
            "trigger=ally_make_same_save(range:5ft),"
            "instant{on_success:none@ally,on_fail:half@ally}}"
        )
    ],
    ("colegio-da-danca", "Bailado Contínuo"): [
        (
            "while_active{requires:ability{acordes_de_poder, classe:bardo}."
            "active,1/turn,instant{cast:ability{bailados_de_combate, "
            "classe:bardo}(without{cost:inspiracao_bardica})}}"
        )
    ],
    ("colegio-da-danca", "Grande Final"): [
        (
            "while_active{trigger=use_bailado{targets:creature},"
            "instant{targets:+1(valid,separate_saves)}}"
        )
    ],
    ("colegio-das-laminas", "Duelista Elegante"): [
        (
            "always_active{prof:weapon{armas_marciais},"
            "pick:arma_mastery:1(reset:long_rest),focus:weapon,"
            "prof:atuacao,trigger=performance_check,"
            "instant{modify:performance_check.attr:=dex"
            "(requires:weapon{cortante,proficient})}}"
        ),
        "swap:long_rest",
    ],
    ("colegio-das-laminas", "Estilo de Luta"): [
        "always_active{pick:opcao:estilo_de_luta:1(swap:level_up)}"
    ],
    ("colegio-das-laminas", "Floreios de Lâmina"): [
        (
            "while_active{trigger=attack_action,"
            "instant{speed:+10ft(duration:until_turn_end)}}"
        ),
        (
            "while_active{1/turn,trigger=hit_attack,requires:weapon,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "pick:floreio:1,define{floreio:list{"
            "defensivo:{dmg:+roll{resource:dado_de_inspiracao},"
            "ca:+roll{resource:dado_de_inspiracao}"
            "(duration:until_next_turn_start)},"
            "movel:{dmg:+roll{resource:dado_de_inspiracao},"
            "push:5ft*roll@target,action:reaction,"
            "move:speed(without{opportunity_attack},end_within:5ft)},"
            "cortante:{dmg:+roll{resource:dado_de_inspiracao},"
            "dmg:roll{resource:dado_de_inspiracao}"
            "@chosen_creature(range:5ft)}}}}}"
        ),
    ],
    ("colegio-das-laminas", "Segundo Ataque"): [
        (
            "always_active{attacks:=2,"
            "instant{replace_attack:cast{spell:pick{nivel:0}"
            "{lista:bardo,casting_time:action,"
            "excludes:ability{segredos_magicos, classe:bardo}}}}}"
        )
    ],
    ("colegio-das-laminas", "Compasso da Lâmina"): [
        (
            "while_active{modify:ability{acordes_de_poder, classe:bardo}."
            "check.attr:=dex(requires:weapon{blade}),"
            "trigger=hit_attack(since:last_turn_start),"
            "instant{modify:presentation.duration:+1_turn}}"
        )
    ],
    ("colegio-das-laminas", "Ritmo Infindável"): [
        (
            "while_active{trigger=use_floreio_de_lamina,"
            "instant{roll:1d6(without{cost:inspiracao_bardica})}}"
        )
    ],
    ("colegio-das-laminas", "Represália Letal"): [
        (
            "while_active{action:reaction,"
            "trigger=hit_by_melee{see_attacker},"
            "instant{attack:melee(adv)@attacker}}"
        ),
        (
            "while_active{trigger=use_floreio_de_lamina,"
            "instant{action:bonus_action,"
            "pick:action:1(from:[dash,disengage])}}"
        ),
        (
            "while_active{trigger=use_floreio_de_lamina,"
            "instant{pick:floreio:+1(distinct,without{extra_cost})}}"
        ),
    ],
    ("colegio-do-fascinio", "Dom de Palco"): [
        "always_active{prof:atuacao,adv:atuacao_check}"
    ],
    ("colegio-do-fascinio", "Manto Deslumbrante"): [
        "action=bonus_action",
        (
            "instant{resource_cost:inspiracao_bardica:1,"
            "pick:allies:max(cha_mod,1)(range:30ft,see),"
            "temp_hp:+roll{resource:dado_de_inspiracao},"
            "grant:move(speed,without{opportunity_attack})}"
        ),
    ],
    ("colegio-do-fascinio", "Presença Hipnótica"): [
        (
            "while_active{requires:perform_1_minute,action:action,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{wis,cd=ability{conjuracao, classe:bardo}.cd}"
            "@chosen_creatures(range:90ft,heard_performance),"
            "on_fail:apply:enfeiticado(duration:hours:1,"
            "ends_on:hostility),"
            "on_success:define{target_unaware}}}"
        )
    ],
    ("colegio-do-fascinio", "Encanto Prolongado"): [
        (
            "while_active{trigger=start{ability{acordes_de_poder, classe:bardo}},"
            "instant{sustain:presentation(without{action},duration:minutes:1)},"
            "restriction{incapacitado}}"
        )
    ],
    ("colegio-do-fascinio", "Visagem de Outro Mundo"): [
        (
            "while_active{trigger=ability{manto_deslumbrante, classe:bardo},"
            "instant{duration:=minutes:1},restriction{incapacitado},"
            "action:bonus_action(1/turn),"
            "instant{pick:efeito_manto:1@creature(range:30ft,see_or_hear),"
            "define{efeito_manto:list{encanto_sutil:"
            "{cast{spell:pick{[enfeiticar-pessoa,comando]},"
            "modifiers{without{slot},duration<=manto}}},"
            "brilho_protetor:{temp_hp:+roll{resource:dado_de_inspiracao},"
            "move:speed(without{opportunity_attack})}}}}}"
        )
    ],
    ("colegio-do-fascinio", "Encanto Reflexo"): [
        (
            "while_active{action:reaction,trigger=hit_by_attack{see_attacker},"
            "instant{if(!ability{manto_deslumbrante, classe:bardo}.active):"
            "resource_cost:inspiracao_bardica:1,"
            "ca:+roll{resource:dado_de_inspiracao}}}"
        )
    ],
    ("colegio-do-fascinio", "Manto de Proteção"): [
        (
            "while_active{requires:{ability{manto_deslumbrante, classe:bardo}."
            "active|ability{acordes_de_poder, classe:bardo}.active},"
            "aura{radius:30ft,target:self+allies,"
            "effects{requires:see_or_hear_you,"
            "adv:save_against{enfeiticado,amedrontado,paralisado,atordoado},"
            "define{see_through_illusions:"
            "spell_level<=max(cha_mod,1)}}}}"
        ),
        (
            "while_active{action:reaction,trigger=initiative,"
            "requires:{!surpreso,!incapacitado},"
            "instant{resource_cost:inspiracao_bardica:1,"
            "cast:ability{manto_deslumbrante, classe:bardo}}}"
        ),
    ],
    ("colegio-do-fascinio", "Presença Majestosa"): [
        (
            "while_active{trigger=cast{spell:pick{escola:encantamento},"
            "target{see_you,range:30ft}},"
            "instant{if(!ability{manto_deslumbrante, classe:bardo}.active):"
            "resource_cost:inspiracao_bardica:1,dadv:save@target}}"
        )
    ],
    ("colegio-dos-espiritos", "Foco Espiritual"): [
        (
            "always_active{focus:[instrumento_musical,vela,bola_de_cristal,"
            "caveira,quadro_espiritual,baralho_de_taro]}"
        ),
        (
            "spell_selection:any{spell:orientacao,extra,fora_do_limite,"
            "modifiers{range:=30ft}}"
        ),
    ],
    ("colegio-dos-espiritos", "Arcanos do Véu"): [
        (
            "while_active{requires:holding{ability{foco_espiritual, classe:bardo}},"
            "action:bonus_action,instant{play:prepared_arcano"
            "(target:creature(range:30ft),discard_after)},"
            "define{draw:roll_unique{dice:1d20},max_prepared:3,"
            "save_cd:ability{conjuracao, classe:bardo}.cd,"
            "effect_die:resource{dado_de_inspiracao},"
            "alternate:cast_linked_spell(without{slot},upcast:spell_slot)}}"
        ),
        (
            "define{arcanos_do_veu:table{"
            "1:{spell:salto,effect:teleport_30ft},"
            "2:{spell:misseis_magicos,effect:dex_save_2dice_energy_plus_cha},"
            "3:{spell:compreender_idiomas,effect:add_die_to_mental_checks_and_detect_hidden},"
            "4:{spell:bom_fruto,effect:temp_hp_die_plus_classlvl_and_speed_10ft},"
            "5:{spell:armadura_arcana,effect:ca_plus_2_adv_str_con_save_immune_push_prone},"
            "6:{spell:identificar,effect:add_die_to_saves},"
            "7:{spell:enfeiticar_pessoa,effect:split_damage_between_two},"
            "8:{spell:passos_longos,effect:dash_or_disengage_no_opportunity},"
            "9:{spell:santuario,effect:invisible_until_action_and_reveal_hidden},"
            "10:{spell:orbe_cromatica,effect:adv_next_d20_reroll_on_fail},"
            "11:{spell:armadura_gelida,effect:cha_save_2dice_radiant_retribution},"
            "12:{spell:graxa,effect:str_save_restrained_or_speed_zero},"
            "13:{spell:infligir_ferimentos,effect:con_save_3dice_necrotic_life_transfer},"
            "14:{spell:curar_ferimentos,effect:heal_2dice_plus_cha_and_cleanse},"
            "15:{spell:tentaculos_abissais,effect:wis_save_2dice_psychic_restrained},"
            "16:{spell:onda_de_trovao,effect:cone_30ft_3dice_fire_break_concentration},"
            "17:{spell:palavra_curativa,effect:heal_2dice_adv_saves},"
            "18:{spell:disfarce_se,effect:invisible_then_necrotic_and_frightened},"
            "19:{spell:raio_guiador,effect:aoe_con_save_2dice_radiant_blinded_reveal},"
            "20:{spell:comando,effect:revive_1_or_heal_2dice_plus_cha}}}"
        ),
    ],
    ("colegio-dos-espiritos", "Sessão de Tarô"): [
        (
            "while_active{trigger=short_rest,trigger=long_rest,"
            "instant{define{ritual:hours:1,participants:willing,"
            "each_draws:3,each_keeps:1(hidden),"
            "use:bonus_action(once,until:long_rest)},"
            "draw:3@self(until:long_rest)},uses{1,reset:long_rest}}"
        )
    ],
    ("colegio-dos-espiritos", "Cartas em Cena"): [
        (
            "while_active{trigger=start{ability{acordes_de_poder, classe:bardo}},"
            "instant{draw:3,define{discard_previous_arcanos:true}},"
            "trigger=sustain{ability{acordes_de_poder, classe:bardo}},"
            "instant{play:prepared_arcano(without{action})},"
            "trigger=cast{spell:pick{lista:bardo},deals_damage_or_heals,"
            "requires:holding{ability{foco_espiritual, classe:bardo}}},"
            "instant{dmg:+roll{resource:dado_de_inspiracao},"
            "heal:+roll{resource:dado_de_inspiracao}}}"
        )
    ],
    ("colegio-dos-espiritos", "Manifestação Espiritual"): [
        (
            "spell_selection:any{spell:guardioes_espirituais,"
            "always_prepared,extra,fora_do_limite}"
        ),
        (
            "cast{spell:guardioes-espirituais,modifiers{without{slot}},"
            "uses{1,reset:long_rest}}"
        ),
        (
            "while_active{trigger=cast{spell:guardioes_espirituais},"
            "instant{aura{target:self+allies,effects{cover:half}},"
            "uses{1,reset:short_or_long_rest}},"
            "define{can_start_with:presentation,"
            "sustain_presentation:sustain_concentration}}"
        ),
    ],
    ("colegio-dos-espiritos", "Conexão Mística"): [
        (
            "while_active{trigger=initiative,instant{draw:3},"
            "trigger=ability{cartas_em_cena, classe:bardo},"
            "instant{roll{dice:resource{dado_de_inspiracao}x2,keep:highest}}}"
        )
    ],
    ("colegio-dos-espiritos", "Arcano Maior"): [
        (
            "while_active{trigger=draw:3,"
            "instant{modify:one_drawn_arcano:=pick:any_arcano}}"
        )
    ],
    ("colegio-skald", "Forja do Skald"): [
        (
            "always_active{prof:weapon{armas_marciais},"
            "prof:armor{escudos,armadura_media,armadura_pesada},"
            "focus:[weapon,shield],pick:opcao:estilo_de_luta:1,"
            "pick:arma_mastery:1(reset:long_rest),"
            "attr:max_hp+3,attr:max_hp+(classlvl - 3)}"
        )
    ],
    ("colegio-skald", "Estrofe de Batalha"): [
        (
            "while_active{trigger=ally_spend_inspiration,"
            "pick:effect:1(from:[defesa,ofensa]),"
            "instant{match(effect){defesa:{action:reaction,"
            "trigger=hit_by_attack,ca:+roll{resource:dado_de_inspiracao}},"
            "ofensa:{trigger=hit_attack,"
            "dmg:+roll{resource:dado_de_inspiracao}}}}}"
        )
    ],
    ("colegio-skald", "Brado de Investida"): [
        (
            "while_active{action:reaction,trigger=initiative,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "aura{radius:30ft,target:chosen_allies,"
            "effects{requires:hear_you,"
            "initiative:+roll{resource:dado_de_inspiracao}}}}}"
        )
    ],
    ("colegio-skald", "Segundo Ataque"): [
        (
            "always_active{attacks:=2,"
            "instant{replace_attack:cast{spell:pick{nivel:0}"
            "{lista:bardo,casting_time:action,"
            "excludes:ability{segredos_magicos, classe:bardo}}}}}"
        )
    ],
    ("colegio-skald", "Saga em Andamento"): [
        (
            "while_active{requires:ability{acordes_de_poder, classe:bardo}."
            "active,trigger=hit_attack,"
            "instant{sustain:presentation(without{action})},"
            "1/turn,instant{resource_cost:inspiracao_bardica:1,"
            "dmg:+roll{resource:dado_de_inspiracao,"
            "dice:match(classlvl){classlvl<14:1,default:2}},"
            "grant:resource{dado_de_inspiracao}:1"
            "@ally(in:presentation_aura)}}"
        )
    ],
    ("colegio-skald", "Hidromel do Valor"): [
        (
            "spell_selection:any{spell:banquete_dos_herois,"
            "always_prepared,extra,fora_do_limite}"
        ),
        (
            "cast{spell:banquete-dos-herois,"
            "modifiers{without{slot},without{material}},uses{1,reset:long_rest}}"
        ),
    ],
    ("colegio-skald", "Runas no Aço"): [
        (
            "while_active{trigger=cast{casting_time:action},"
            "action:bonus_action,instant{attack:weapon}}"
        )
    ],
    ("colegio-skald", "Coro das Sagas"): [
        (
            "while_active{trigger=ability{brado_de_investida, classe:bardo},"
            "instant{grant:resource{dado_de_inspiracao}:1@each_ally},"
            "action:reaction,trigger=ally_drop_to_0(range:30ft),"
            "instant{resource_cost:inspiracao_bardica:1,"
            "cast:ability{brado_de_investida, classe:bardo}}}"
        )
    ],
}

ACCORDS = {
    "Toada da Pressa": (2, [
        (
            "while_active{aura{radius:30ft,target:allies,"
            "effects{speed:match(presentation_grade){minor:10ft,"
            "major:max(10ft,5ft*cha_mod)},"
            "if(presentation_grade=major):ignore:difficult_terrain}}}"
        )
    ]),
    "Cântico de Coragem": (2, [
        (
            "while_active{aura{radius:30ft,target:allies,"
            "effects{adv:next_save"
            "(match(presentation_grade){minor:amedrontado,"
            "major:{amedrontado,enfeiticado}}),"
            "if(presentation_grade=major):"
            "cleanse:one{amedrontado,enfeiticado}}}}"
        )
    ]),
    "Cântico Confundidor": (2, [
        (
            "while_active{aura{radius:30ft,target:enemies,"
            "effects{save{wis,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{speed:*0.5,"
            "if(presentation_grade=major):restricts{reaction}}}}}"
        )
    ]),
    "Canção de Descanso": (2, [
        (
            "while_active{trigger=short_rest,"
            "instant{resource_cost:inspiracao_bardica:any,"
            "heal:sum(rolled_inspiration_dice)@allies(distribute),"
            "if(presentation_grade=major):heal:+cha_mod@each},"
            "define{each_target:1/long_rest}}"
        )
    ]),
    "Melodia Inspiradora": (6, [
        (
            "while_active{trigger=presentation{start,sustain},"
            "instant{temp_hp:match(presentation_grade){"
            "minor:roll{resource:dado_de_inspiracao},"
            "major:max{resource:dado_de_inspiracao}+cha_mod}"
            "@allies(in:presentation_aura)}}"
        )
    ]),
    "Estrofe Marcial": (6, [
        (
            "while_active{1/turn,trigger=ally_hit_attack(in:presentation_aura),"
            "instant{dmg:match(presentation_grade){minor:max(cha_mod,1),"
            "major:max(cha_mod,1)+roll{resource:dado_de_inspiracao}}"
            "(trovejante)}}"
        )
    ]),
    "Réquiem Desorientador": (6, [
        (
            "while_active{aura{radius:30ft,target:enemies,"
            "effects{save{wis,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{next_save:dadv"
            "(minor:wis_only,major:any_including_concentration)}}}}"
        )
    ]),
    "Contraponto": (6, [
        (
            "while_active{action:reaction,"
            "trigger=cast{spell:active,range:30ft,see_or_hear},"
            "instant{resource_cost:inspiracao_bardica:1,"
            "ability_check:cha(atuacao),"
            "modify:spell_damage:-match(presentation_grade){"
            "minor:roll{resource:dado_de_inspiracao}+cha_mod,"
            "major:half}@self+allies}}"
        )
    ]),
    "Refrão do Baluarte": (10, [
        (
            "while_active{1/round,trigger=first_attack_against_ally"
            "(in:presentation_aura),"
            "instant{cover:match(presentation_grade){minor:half,"
            "major:three_quarters}}}"
        )
    ]),
    "Odisséia": (10, [
        (
            "while_active{trigger=start_presentation,"
            "instant{grant:heroic_inspiration@"
            "match(presentation_grade){minor:one_ally,major:all_allies}"
            "(in:presentation_aura)}}"
        )
    ]),
    "Toada Irritante": (10, [
        (
            "while_active{aura{radius:30ft,target:enemies,"
            "effects{save{wis,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{next_attack:dadv"
            "(minor:against_other_than_self,major:any_target)}}}}"
        )
    ]),
    "Hino da Confiança": (18, [
        (
            "while_active{aura{radius:30ft,target:allies,"
            "effects{roll_add:+roll{resource:dado_de_inspiracao}@next_save,"
            "if(presentation_grade=major):adv:next_save}}}"
        )
    ]),
    "Dissonância Aterradora": (18, [
        (
            "while_active{aura{radius:30ft,target:enemies,"
            "effects{save{wis,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:apply:match(presentation_grade){"
            "minor:amedrontado,major:atordoado}"
            "(duration:until_next_turn_start)}}}"
        )
    ]),
    "Acorde Lendário": (18, [
        (
            "while_active{trigger=start_presentation,"
            "instant{pick:allies:max(cha_mod,1)(in:presentation_aura),"
            "grant:extra_action(next_turn,"
            "minor:attack_only,major:{attack_or_cantrip,attack_adv})},"
            "define{not{sustained}:true}}"
        )
    ]),
}

BAILADOS = {
    "Roda Baixa de Três Tempos": [
        (
            "while_active{1/turn,trigger=enter_melee_range,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{dex,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{apply:caido,"
            "move:10ft@ally(range:5ft,without{opportunity_attack}),"
            "without{opportunity_attack}@self}}}"
        )
    ],
    "Galliarda Conduzida": [
        (
            "while_active{1/turn,trigger=end_move(range:5ft),"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{str,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{move:10ft@target,move:10ft@self"
            "(without{opportunity_attack})}}}"
        )
    ],
    "Esquiva em Arabesque": [
        (
            "while_active{action:reaction,trigger=targeted_by_attack{see},"
            "instant{resource_cost:inspiracao_bardica:1,dadv:attack,"
            "on:miss -> move:half_speed(without{opportunity_attack})}}"
        )
    ],
    "Convite à Dança": [
        (
            "while_active{action:bonus_action,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{wis,cd=ability{conjuracao, classe:bardo}.cd}"
            "@enemy(range:30ft,see_you),"
            "on_fail:{dadv:attack(against:other_than_self),"
            "restricts{move_away_from_self},"
            "duration:until_next_turn_start}}}"
        )
    ],
    "Descompasso": [
        (
            "while_active{1/turn,trigger=end_move(range:5ft),"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{cha,cd=ability{conjuracao, classe:bardo}.cd},"
            "on_fail:{adv:first_attack_against_target,"
            "restricts{choose:action_or_bonus_action},"
            "duration:until_next_turn_start}}}"
        )
    ],
    "Meia-Lua": [
        (
            "while_active{1/turn,action:bonus_action,"
            "requires:move>=half_speed,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "aoe{radius:5ft,dmg:roll{resource:dado_de_inspiracao}"
            "(psiquico),speed:-10ft(duration:until_target_turn_end)}}}"
        )
    ],
    "Tropeço Mascarado": [
        (
            "while_active{action:reaction,"
            "trigger=ally_targeted_by_attack(range:5ft),"
            "instant{resource_cost:inspiracao_bardica:1,"
            "cover:half@ally,on:hit -> "
            "modify:damage_taken:-roll{resource:dado_de_inspiracao}}}"
        )
    ],
    "Adágio": [
        (
            "while_active{action:bonus_action,"
            "instant{resource_cost:inspiracao_bardica:1,"
            "save{dex,cd=ability{conjuracao, classe:bardo}.cd}"
            "@creature(range:30ft,see),"
            "on_fail:{speed:*0.5,restricts{reaction},"
            "duration:until_next_turn_start}}}"
        )
    ],
}

UNTAGGED_ALLOWED = {
    (None, "Colégio de Bardo"),
    (None, "Aprimoramento de Atributo ou Talento"),
}
