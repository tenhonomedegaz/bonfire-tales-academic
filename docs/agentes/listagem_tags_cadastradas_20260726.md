# Listagem completa das tags cadastradas

Gerado diretamente de `home/tag_library.json` e cruzado com o banco local.
A contagem e textual e inclui classes, habilidades, talentos, opcoes,
tracos raciais, antecedentes, magias, bestiario e itens mundanos/magicos.

## Resumo

- Registros lidos: 4464
- Registros com tags: 3269
- Linhas de formula: 10085
- Entradas cadastradas: 521
- Nomes ativos com hifen: 0
- Termos proibidos ainda usados: 0
- Entradas estruturais sem uso atual: 21

## Grupos

| Grupo | Entradas |
|---|---:|
| `catalogs` | 11 |
| `catalogs.caster_fraction.valores` | 4 |
| `catalogs.condition.valores` | 20 |
| `catalogs.creature_type.valores` | 14 |
| `catalogs.damage_type.valores` | 13 |
| `catalogs.equipment_category.valores` | 7 |
| `catalogs.sense_type.valores` | 6 |
| `catalogs.size.valores` | 6 |
| `catalogs.weapon_property.valores` | 18 |
| `conditions` | 14 |
| `definicoes_inline` | 5 |
| `escolhas` | 7 |
| `events` | 46 |
| `forbidden_heads` | 3 |
| `forbidden_operands` | 2 |
| `functions` | 10 |
| `functions.limiters` | 8 |
| `functions.operadores` | 5 |
| `functions.variaveis_de_formula` | 18 |
| `ops` | 28 |
| `primitives` | 219 |
| `recursos_universais` | 2 |
| `references` | 10 |
| `scopes.atributo` | 2 |
| `scopes.defensivo` | 1 |
| `scopes.direcao_ataque` | 2 |
| `scopes.distancia` | 2 |
| `scopes.empunhadura` | 4 |
| `scopes.qualificadores_de_arma` | 2 |
| `scopes.rolagem_magica` | 1 |
| `scopes.situacional` | 3 |
| `scopes.tipo_fisico` | 4 |
| `selectors` | 16 |
| `tags_de_classe` | 8 |

## Vocabulario

### `catalogs`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `caster_fraction` | 0 | - | lang=en | - |
| `condition` | 23 | classe-hab, opcao, talento, traco | lang=pt | - |
| `creature_type` | 32 | classe-hab, item-magico, opcao, talento, traco | lang=pt | - |
| `damage_type` | 4 | talento, traco | lang=pt | - |
| `equipment_category` | 1 | talento | lang=pt | - |
| `idioma` | 12 | classe-hab, item-magico, talento, traco | lang=pt; fonte=lista de idiomas do sistema | - |
| `referencias_de_banco` | 0 | - | - | - |
| `sense_type` | 0 | - | lang=en | - |
| `size` | 41 | bestiario, classe-hab, opcao, talento, traco | lang=pt | - |
| `skill` | 16 | item-magico, talento, traco | lang=pt; fonte_db=catálogo de perícias (18) | - |
| `weapon_property` | 0 | - | lang=pt | - |
### `catalogs.caster_fraction.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `full` | 14 | classe-hab, magia, traco | - | Valor fechado do catalogo caster_fraction. |
| `half` | 216 | classe, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo caster_fraction. |
| `pact` | 2 | classe-hab | - | Valor fechado do catalogo caster_fraction. |
| `third` | 2 | classe-hab | - | Valor fechado do catalogo caster_fraction. |
### `catalogs.condition.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `agarrado` | 13 | classe-hab, item-magico, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `amedrontado` | 97 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `atordoado` | 21 | classe-hab, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `banido` | 2 | classe-hab, opcao | - | Valor fechado do catalogo condition. |
| `caido` | 53 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `cego` | 39 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `doente` | 13 | bestiario, classe-hab, item-magico, magia, traco | - | Valor fechado do catalogo condition. |
| `enfeiticado` | 91 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `envenenado` | 46 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `exaustao` | 14 | bestiario, classe-hab, talento, traco | - | Valor fechado do catalogo condition. |
| `incapacitado` | 46 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `inconsciente` | 22 | classe-hab, item-mundano, magia, opcao, traco | - | Valor fechado do catalogo condition. |
| `invisivel` | 33 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo condition. |
| `paralisado` | 20 | classe-hab, item-mundano, magia, talento, traco | - | Valor fechado do catalogo condition. |
| `petrificado` | 6 | item-magico, magia, traco | - | Valor fechado do catalogo condition. |
| `possuido` | 4 | classe-hab, talento | - | Valor fechado do catalogo condition. |
| `queimando` | 1 | talento | - | Valor fechado do catalogo condition. |
| `restringido` | 26 | classe-hab, magia, opcao, traco | - | Valor fechado do catalogo condition. |
| `silenciado` | 2 | classe-hab, opcao | - | Valor fechado do catalogo condition. |
| `surdo` | 14 | classe-hab, magia, opcao, talento | - | Valor fechado do catalogo condition. |
### `catalogs.creature_type.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `aberracao` | 5 | classe-hab, item-magico | - | Valor fechado do catalogo creature_type. |
| `besta` | 16 | classe-hab, magia, opcao, talento, traco | - | Valor fechado do catalogo creature_type. |
| `celestial` | 31 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `construto` | 7 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `corruptor` | 14 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `dragao` | 13 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `elemental` | 18 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `fada` | 7 | classe-hab, item-magico | - | Valor fechado do catalogo creature_type. |
| `gigante` | 3 | classe-hab, item-magico | - | Valor fechado do catalogo creature_type. |
| `humanoide` | 2 | classe-hab, traco | - | Valor fechado do catalogo creature_type. |
| `limo` | 0 | - | - | Valor fechado do catalogo creature_type. |
| `monstruosidade` | 2 | talento | - | Valor fechado do catalogo creature_type. |
| `morto_vivo` | 23 | classe-hab, item-magico, traco | - | Valor fechado do catalogo creature_type. |
| `planta` | 4 | classe-hab, traco | - | Valor fechado do catalogo creature_type. |
### `catalogs.damage_type.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `acido` | 65 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `concussao` | 75 | bestiario, classe-hab, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `cortante` | 62 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `fogo` | 145 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `forca` | 108 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `frio` | 86 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `necrotico` | 106 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `perfurante` | 84 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `psiquico` | 97 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `radiante` | 95 | classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `raio` | 88 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `trovejante` | 73 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
| `veneno` | 59 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Valor fechado do catalogo damage_type. |
### `catalogs.equipment_category.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `armadura_leve` | 19 | classe | - | Valor fechado do catalogo equipment_category. |
| `armadura_media` | 19 | classe, classe-hab, talento, traco | - | Valor fechado do catalogo equipment_category. |
| `armadura_pesada` | 10 | classe, classe-hab, traco | - | Valor fechado do catalogo equipment_category. |
| `armas_marciais` | 13 | classe, classe-hab, talento | - | Valor fechado do catalogo equipment_category. |
| `armas_simples` | 19 | classe, talento | - | Valor fechado do catalogo equipment_category. |
| `escudos` | 18 | classe, classe-hab, talento | - | Valor fechado do catalogo equipment_category. |
| `instrumento_musical` | 5 | classe-hab, talento | - | Valor fechado do catalogo equipment_category. |
### `catalogs.sense_type.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `blindsight` | 24 | classe-hab, item-magico, opcao, talento, traco | - | Valor fechado do catalogo sense_type. |
| `darkvision` | 74 | bestiario, classe-hab, item-magico, magia, opcao, traco | - | Valor fechado do catalogo sense_type. |
| `devilsight` | 28 | bestiario, classe-hab, opcao, traco | - | Valor fechado do catalogo sense_type. |
| `ethereal` | 3 | classe-hab, item-magico | - | Valor fechado do catalogo sense_type. |
| `tremorsense` | 8 | classe-hab, traco | - | Valor fechado do catalogo sense_type. |
| `truesight` | 13 | classe-hab, item-magico, magia, opcao, traco | - | Valor fechado do catalogo sense_type. |
### `catalogs.size.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `descomunal` | 2 | bestiario, classe-hab | - | Valor fechado do catalogo size. |
| `enorme` | 8 | bestiario, classe-hab, talento, traco | - | Valor fechado do catalogo size. |
| `grande` | 19 | bestiario, classe-hab, opcao, traco | - | Valor fechado do catalogo size. |
| `medio` | 4 | bestiario, classe-hab | - | Valor fechado do catalogo size. |
| `miudo` | 3 | bestiario, classe-hab | - | Valor fechado do catalogo size. |
| `pequeno` | 2 | bestiario, classe-hab | - | Valor fechado do catalogo size. |
### `catalogs.weapon_property.valores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `acuidade` | 21 | classe-hab, item-mundano, talento | - | Valor fechado do catalogo weapon_property. |
| `adaptavel` | 3 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `alcance` | 9 | classe-hab, item-mundano | - | Valor fechado do catalogo weapon_property. |
| `arma_dupla` | 7 | item-mundano, talento | - | Valor fechado do catalogo weapon_property. |
| `arremesso` | 23 | classe-hab, item-mundano, opcao, talento | - | Valor fechado do catalogo weapon_property. |
| `carregar` | 7 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `composto` | 1 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `duas_maos` | 24 | classe-hab, item-mundano, opcao, talento | - | Valor fechado do catalogo weapon_property. |
| `empunhadura_longa` | 6 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `leve` | 28 | classe-hab, item-mundano, opcao, talento, traco | - | Valor fechado do catalogo weapon_property. |
| `municao` | 17 | classe-hab, item-mundano | - | Valor fechado do catalogo weapon_property. |
| `pareada` | 1 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `pesada` | 22 | classe-hab, item-mundano, talento, traco | - | Valor fechado do catalogo weapon_property. |
| `recarga` | 3 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `retorna` | 5 | classe-hab, opcao | - | Valor fechado do catalogo weapon_property. |
| `sutil` | 0 | - | - | Valor fechado do catalogo weapon_property. |
| `tecnica` | 3 | item-mundano | - | Valor fechado do catalogo weapon_property. |
| `versatil` | 11 | item-mundano, opcao, talento | - | Valor fechado do catalogo weapon_property. |
### `conditions`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `adv` | 328 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | você tem Vantagem na rolagem |
| `ally(range:<dist>)` | 0 | - | - | há um aliado a até <dist> ft |
| `banished` | 0 | - | - | o alvo está banido/removido do mapa (até um evento) |
| `combinadores` | 0 | - | - | requires:{a and b \| c} — AND/OR entre condições (ex.: Ataque Furtivo: {adv \| ally(range:5ft) and not{dadv}}) |
| `in:ability{<nome>}` | 0 | - | - | você está sob efeito ativo de uma habilidade própria referenciada (ex.: in:ability{forma_do_terror}) |
| `in_dim_light` | 20 | classe-hab, item-magico, opcao, traco | - | você está em Luz Fraca ou Escuridão (par de in_light) |
| `moved_by_other` | 4 | item-magico, talento | - | você foi movido por uma força/criatura externa neste turno (predicado defensivo). Aprovado 2026_06_18. |
| `next_attack` | 34 | classe-hab, opcao, talento, traco | - | escopo: a próxima jogada de ataque deste turno |
| `route_exists` | 3 | classe-hab | - | há uma rota válida para executar o movimento forçado ou concedido |
| `sangrando` | 10 | talento, traco | - | a criatura está Sangrando (Bloodied — metade ou menos do PV máximo). Predicado: requires:target{sangrando} (Atacante Selvagem). Aprovado 2026_06_18. |
| `target{!acted}` | 0 | - | - | o alvo ainda não agiu no combate |
| `target{acted}` | 0 | - | - | o alvo já agiu no combate |
| `target{same}` | 0 | - | - | a MESMA criatura do gatilho (ex.: Ataque Estudado — vantagem contra quem você errou) |
| `target{surprised}` | 0 | - | - | o alvo está Surpreso |
### `definicoes_inline`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `expor_variavel` | 0 | - | - | define{dmg_bonus: roundup(classlvl/2)} — exposto como ability{<dona>, classe:<slug>}.dmg_bonus |
| `list` | 29 | classe-hab, magia, talento, traco | - | - |
| `pool` | 0 | - | - | - |
| `table` | 10 | classe-hab, talento | - | - |
| `weapon` | 466 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | - |
### `escolhas`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `N_de_recurso` | 0 | - | - | pick:arma:N(=recurso maestria_com_armas) — Maestria de Arma escolhe ARMAS (não maestrias abstratas); cada arma dá acesso a todas as maestrias dela, 1 por ataque |
| `pick:<local>:N` | 0 | - | - | escolhe de algo definido por define{} (ex.: pick:aspecto_selvagem:1) |
| `pick:opcao:<tipo>:N` | 0 | - | - | escolhe N de TB_OpcaoJogo do tipo (acesso via TB_AcessoOpcao) |
| `pick:pericia:N \| pick:idioma:N \| pick:ferramenta:N` | 0 | - | - | escolhe de listas_catálogo |
| `pick:pericia_expertise:{<nivel>:<qtd>}` | 0 | - | - | marca perícias p/ expertise (motor dobra PB — regra global) |
| `pick:spell_mod:{int\|wis\|cha}` | 0 | - | - | o jogador escolhe o atributo de conjuração de uma magia concedida por talento (par de spell_mod:asi_attr). Aprovado 2026_06_18. |
| `progressao` | 0 | - | - | pick:pericia:{classlvl=5:1, classlvl=10:1} acumula por nível |
### `events`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `after_attack_action` | 12 | opcao, talento, traco | - | imediatamente após realizar a Ação de Atacar (gatilho de ação bônus) |
| `ally_drop_to_0` | 5 | classe-hab, traco | - | um aliado cai a 0 PV |
| `ally_fail_save` | 1 | classe-hab | - | um aliado falha num teste de resistência |
| `ally_spend_inspiration` | 2 | classe-hab, talento | - | um aliado gasta uma Inspiração Heroica (Fólio Incansável) — aprovado 2026_06_18 |
| `ally_take_damage` | 13 | classe-hab, opcao, talento, traco | - | um aliado sofre dano |
| `attack_action` | 51 | classe-hab, opcao, traco | - | você realiza a Ação de Atacar (≠ ability — é a ação genérica; substitui ability{ataque}) — aprovado 2026_06_18 |
| `attack_roll` | 25 | classe-hab, item-magico, opcao, talento, traco | - | ao rolar uma jogada de ataque (antes do resultado; par de save_roll) |
| `creature_dies` | 3 | classe-hab, traco | - | uma criatura morre (ex.: in_aura — Sacerdote da Passagem) |
| `crit_melee` | 8 | classe-hab, item-magico, talento, traco | - | crítico corpo a corpo |
| `death_save` | 10 | item-magico, talento, traco | - | uma criatura faz um Teste contra a Morte (ver primitives.death_save) — aprovado 2026_06_18 |
| `dodge_action` | 2 | traco | - | você realiza a Ação Esquivar (substitui ability{dodge}) — aprovado 2026_06_18 |
| `drop_to_0` | 20 | bestiario, classe-hab, opcao, traco | - | cai a 0 PV |
| `end` | 35 | classe-hab, opcao, traco | - | fim da duração ativa da PRÓPRIA habilidade (on:end) |
| `enemy_end_turn` | 4 | opcao, traco | - | um inimigo termina o turno (no alcance/zona dado) |
| `enemy_enters_aura` | 1 | traco | - | um inimigo entra numa aura referenciada |
| `enemy_enters_reach` | 3 | opcao, talento | - | um inimigo entra no alcance corpo a corpo da sua arma |
| `enemy_heals` | 1 | classe-hab | - | um inimigo é curado (Sopro de Nascira) |
| `enemy_moves_within_aura` | 1 | traco | - | um inimigo se move dentro de uma aura referenciada |
| `enter_area` | 4 | opcao | - | uma criatura entra numa área/zona criada por você (família: enter_area_or_move, enter_area_or_turn_start) |
| `enter_aura` | 5 | classe-hab, opcao | - | entra numa aura |
| `fail_again` | 1 | classe-hab | - | o dado/re_rolagem adicionado pela característica também falha (2ª falha consecutiva — Perícia Inigualável) — aprovado 2026_06_18 |
| `fail_check` | 10 | classe-hab, talento, traco | - | falha num teste de perícia/habilidade (par de fail_save — aprovado 2026_06_17) |
| `fail_save` | 30 | classe-hab, item-magico, opcao, talento, traco | - | falha num teste de resistência |
| `first_attack` | 2 | classe-hab, traco | - | primeiro ataque do turno |
| `first_turn` | 7 | classe-hab | - | primeiro turno do personagem no combate (aprovado 2026_06_17) |
| `hide_action` | 1 | classe-hab | - | você realiza a Ação Esconder_se (substitui ability{esconder}) — aprovado 2026_06_18 |
| `hit_by_attack` | 33 | bestiario, classe-hab, item-magico, talento, traco | - | é acertado por qualquer ataque (melee ou ranged) |
| `hit_by_melee` | 11 | classe-hab, item-magico, talento, traco | - | é acertado por ataque corpo a corpo |
| `hit_by_ranged` | 0 | - | - | é acertado por ataque à distância |
| `hit_melee` | 59 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | acerta corpo a corpo |
| `hit_thrown` | 5 | classe-hab, item-magico, opcao | - | acerta com arma de arremesso |
| `initiative` | 52 | classe-hab, item-magico, magia, opcao, talento, traco | - | rola iniciativa |
| `long_rest` | 1308 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | descanso longo |
| `magic.deal_dmg` | 0 | - | - | uma magia/truque SEU causou dano a uma criatura |
| `miss` | 24 | bestiario, classe-hab, opcao, talento | - | erra um ataque OU um ataque contra você erra (bidirecional — aprovado 2026_06_17) |
| `overuse` | 3 | classe-hab | - | usar uma característica ALÉM dos usos gratuitos (ex.: exaustão no 2º uso — Paradoxo da Repetição) |
| `reduce_to_0` | 12 | classe-hab, talento, traco | - | reduz alvo a 0 PV |
| `save_roll` | 14 | classe-hab, opcao, talento, traco | - | o ato de rolar um teste de resistência (antes do resultado; p/ reação de aliado) |
| `short_rest` | 63 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | descanso curto |
| `succeed_save` | 11 | classe-hab, talento, traco | - | você (ou aliado) obtém sucesso num teste de resistência |
| `take_damage` | 57 | classe-hab, item-magico, opcao, talento, traco | - | sofre dano |
| `target_attacks` | 14 | classe-hab, opcao, talento, traco | - | uma criatura faz um ataque (contra você ou aliado) |
| `target_drop_to_0` | 4 | classe-hab, item-magico, opcao, traco | - | o alvo (marcado/escolhido) cai a 0 PV |
| `target_miss` | 1 | opcao | - | o alvo erra um ataque |
| `turn_end` | 45 | bestiario, classe-hab, item-magico, item-mundano, opcao, talento, traco | - | fim do turno |
| `turn_start` | 47 | classe-hab, opcao, traco | - | início do turno |
### `forbidden_heads`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `patente` | 0 | - | - | Autoridade social e acesso institucional dependem do mestre; ficam apenas na descrição. |
| `recall` | 0 | - | - | Conhecimento narrativo de tema não produz operação determinística; fica apenas na descrição. |
| `rede` | 0 | - | - | Rede social, contatos e favores dependem de interpretação de RP; ficam apenas na descrição. |
### `forbidden_operands`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `conversar_com_nobres` | 0 | - | - | Conversa e status social dependem de interpretação de RP; a perícia é escolhida pelo mestre. |
| `recall_info` | 0 | - | - | Lembrar informação é coberto pela ação genérica study; não crie um contexto exclusivo para uma frase. |
### `functions`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `dados` | 0 | - | - | Notação de dados padrão de VTT (opera sobre o dado, como um operador). 'NdX' = N dados de X faces. Modificadores de descarte: 'dK' descarta os K MENORES (mantém os maiores); 'dhK' descarta os K MAIORES (mantém os menores). Aliases explícitos: 'khK' = mantém os K maiores, 'klK' = mantém os K menores. Ex.: 4d6d1 = rola 4d6 e descarta o menor (mantém os 3 maiores) = 4d6kh3; 4d6dh1 = descarta o maior; 4d6d2 = descarta os 2 menores. Válido em qualquer lugar que aceite <NdX> (dmg, roll{dice}, table, fórmulas). |
| `if` | 118 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | Ramo condicional. |
| `match` | 88 | bestiario, classe-hab, opcao, talento, traco | - | Switch: escolhe EXATAMENTE um ramo (o primeiro que casa). Evita dupla aplicação em categorias que se sobrepõem. |
| `max` | 183 | antecedente, bestiario, classe-hab, item-magico, opcao, talento, traco | - | Máximo / teto. |
| `min` | 39 | antecedente, classe-hab, item-magico, item-mundano, talento, traco | - | Mínimo / piso. |
| `roll` | 92 | antecedente, bestiario, classe-hab, item-magico, opcao, talento, traco | - | Rolagem genérica (tabela ou dados); 'keep' modela 'rola 2 escolhe 1' sem mecânica nova. |
| `rounddown` | 41 | bestiario, classe-hab, opcao, talento, traco | - | Arredonda pra baixo. |
| `roundup` | 23 | classe-hab, opcao, talento, traco | - | Arredonda pra cima. |
| `save` | 618 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | Rola teste de resistência; vale como condição (sucesso/falha). |
| `uses` | 1225 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | Nº de vezes que a habilidade foi usada (valor dinâmico). |
### `functions.limiters`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `1/<reset>{per:<chave>}` | 0 | - | - | uma vez por janela, por sub_chave (ex.: 1/long_rest{per:ciclo}) |
| `1/attack` | 0 | - | - | uma vez por ataque (ex.: 1 manobra por ataque) |
| `1/combat` | 0 | - | - | uma vez por combate |
| `1/long_rest` | 0 | - | - | uma vez por descanso longo |
| `1/round` | 0 | - | - | uma vez por RODADA (resseta no início do próprio turno; difere de 1/turn p/ reações que ocorrem fora do seu turno). Aprovado 2026_06_25. |
| `1/spell` | 0 | - | - | uma vez por feitiço conjurado (ex.: 1 metamagia por magia) |
| `1/turn` | 0 | - | - | uma vez por turno |
| `N/<reset>` | 0 | - | - | N vezes por janela de reset |
### `functions.operadores`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `+ _ * /` | 0 | - | - | aritmética em fórmulas |
| `:+` | 0 | - | - | add (soma/acumula/empilha) |
| `:=` | 0 | - | - | set (sobrescreve, não acumula) |
| `=` | 0 | - | - | bind (vínculo/fórmula/identidade) |
| `@` | 0 | - | - | destinatário: redireciona o efeito imediatamente anterior para o seletor (ex.: move:15ft@target, grant:resource{dado_de_inspiracao}:1@ally(range:60ft), mark{...}@chosen_creature) |
### `functions.variaveis_de_formula`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `aliados_aceitos` | 0 | - | - | nº de aliados voluntários que aceitaram |
| `atributos` | 0 | - | - | str/dex/con/int/wis/cha + -mod \| -score \| -save \| -check |
| `ciclo` | 9 | classe-hab | - | contador de ciclo de gasto de recurso (Conjuração Elemental); par de 'spent' e do limiter 1/<reset>{per:ciclo}. Aprovado 2026_06_18. |
| `classlvl` | 375 | bestiario, classe-hab, opcao | - | nível DA classe |
| `damage_dealt` | 6 | classe-hab, traco | - | dano que você causou (gatilho/fórmula) |
| `damage_taken` | 2 | classe-hab, opcao | - | dano que você sofreu (ex.: redirect/reflect) |
| `ft_moved` | 1 | classe-hab | - | pés percorridos nesta ação (ex.: dmg = 2*ft_moved) |
| `grau` | 1 | classe-hab | - | nível/grau de uma trilha de opção (Virtudes: grau>=2). Gate de progressão, análogo a classlvl. Aprovado 2026_06_18. |
| `lvl` | 46 | talento, traco | - | nível total |
| `marks` | 2 | classe-hab, traco | - | nº de marcas acumuladas |
| `owner_max_hp` | 1 | classe-hab | - | PV máximo do invocador/dono (ex.: threshold:owner_max_hp do Selo de Céssira) |
| `pb` | 280 | antecedente, bestiario, classe-hab, opcao, talento, traco | - | bônus de proficiência |
| `self.cd` | 0 | - | - | a CD da própria habilidade (dentro de um define) |
| `sintonizacao_ativa` | 1 | classe-hab | - | nº de itens mágicos atualmente sintonizados (Magnum Opus) |
| `spell_level` | 34 | bestiario, classe-hab, opcao, talento, traco | - | nível do espaço/magia conjurada (custo do Dom da Criação = PF igual ao nível) |
| `spell_mod` | 191 | bestiario, classe-hab, magia, talento, traco | - | modificador de conjuração |
| `spent` | 2 | classe-hab | - | quantidade efetivamente gasta de um recurso nesta ativação (par de ciclo_gasto; Virtudes/Metamagia) |
| `talent_attr` | 0 | - | - | o atributo que ESTE talento aumenta (asi_attr); usado na CD da habilidade do talento: cd=8+pb+talent_attr_mod. Sufixos -mod/-score. Aprovado 2026_06_18. |
### `ops`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `absorb_damage` | 0 | - | - | Em vez de SOFRER o dano do tipo dado, absorve_o (passa a ter resistência/imunidade situacional). Ex.: Absorver Elementos. |
| `add_damage` | 0 | - | - | Adiciona dado/tipo de dano a um perfil de ataque ou escopo. |
| `add_modifier` | 0 | - | - | Soma um modificador numérico/dado a um valor derivado (acumula). Operador ':+'. |
| `add_to_set` | 1 | classe-hab | - | Adiciona um valor a uma coleção do estado. |
| `alter_attribute` | 0 | - | - | Altera valor ou teto de um atributo. |
| `apply_condition` | 0 | - | - | Aplica uma condição a um alvo (com save/duração opcionais). |
| `cast_spell` | 2 | talento | - | Concede conjuração de uma magia com modificadores. |
| `declare_caster` | 0 | - | - | Declara a conjuração da classe (fração de caster p/ multiclasse). |
| `define` | 145 | antecedente, bestiario, classe-hab, magia, opcao, talento, traco | - | Registra um método/tabela/lista/arma local, referenciável depois. |
| `emit_area` | 0 | - | - | Emite área: aura contínua ou aoe pontual. |
| `gate` | 0 | - | - | Condição de porteiro: restriction (NÃO pode) / requires (exige) / equiped. |
| `grant_execution` | 0 | - | - | Concede uma execução acionável (dash, attack, teleport...) por um custo de ação. |
| `grant_proficiency` | 0 | - | - | Concede proficiência/expertise (perícia, save, armadura, arma, ferramenta). |
| `grant_roll_mod` | 1 | classe-hab | - | Concede vantagem/desvantagem/min/reroll numa rolagem (save/check/attack). |
| `heal` | 151 | antecedente, bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | Cura / concede PV temporário. |
| `mark` | 37 | bestiario, classe-hab, opcao, traco | - | Acumula/consome contadores em alvos. |
| `meta` | 0 | - | - | Marcador/metadado lido pela APLICAÇÃO (UI, edição de ficha), sem efeito no estado derivado pelo motor. Ex.: 'trocavel' marca que a escolha concedida pode ser refeita pelo jogador. |
| `omit` | 0 | - | - | Remove uma etapa, custo, componente, rolagem ou consequência da execução que contém without{}, sem criar estado persistente. |
| `override` | 0 | - | - | Sobrescreve propriedade de uma entidade referenciada (modify:). |
| `pick` | 488 | antecedente, bestiario, classe, classe-hab, essencia, item-magico, magia, opcao, talento, traco | - | Abre N escolhas de um catálogo/lista/opção. |
| `predicate_not` | 0 | - | - | Inverte o valor lógico de um predicado dentro de requires/restriction/if/unless. Não produz efeito no estado. |
| `resource` | 194 | classe-hab, opcao, talento, traco | - | Gasta/restaura/lê um recurso. NÃO declara pool: o pool de recurso de classe vive na TB_RecursoClasse (veto do PO 2026_06_17). A tag só referencia/gasta/restaura. O papel do pool fica em TbRecursoclasse.tipo: table_only, consumable ou choice. |
| `restrict` | 1 | talento | - | Impõe uma proibição enquanto o escopo ativo durar. Diferente de gate: não bloqueia a ativação do próprio efeito, cria uma restrição no personagem/alvo. Ex.: restricts{spellcasting, concentration}. |
| `roll_table` | 0 | - | - | Rola numa tabela definida (define{} table{}). |
| `set_property` | 0 | - | - | Define uma propriedade nomeada de um objeto de estado usando operando chave=valor, sem criar uma operação específica para cada propriedade. |
| `set_value` | 0 | - | - | Sobrescreve um valor (não acumula). Operador ':=' ou '='. |
| `summon` | 71 | antecedente, bestiario, classe-hab, item-magico, magia, traco | - | Invoca criatura(s) controlável(is) referenciando o BESTIÁRIO (o statblock vive lá, não na tag). Ver references.bestiary. |
| `suppress` | 62 | classe-hab, essencia, item-magico, opcao, talento, traco | - | Desativa um efeito, modificador ou regra no escopo atual, sem impedir a ação que poderia produzi-lo. |
### `primitives`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `ability` | 578 | bestiario, classe, classe-hab, item-magico, opcao, talento, traco | forma=reference | Referência (ver references.ability). Não é efeito; resolve um valor/estado. |
| `absorb` | 4 | classe-hab, traco | forma=key_value; op=absorb_damage; target=resistencias | absorb:<dano> — em vez de sofrer o dano daquele tipo, anula e cura PV igual ao dano que sofreria. Usado nas Investiduras (nv17) quando o personagem JA e Imune ao tipo. Aprovado 2026_06_22 (Essencia Elemental, versao final). |
| `action` | 895 | antecedente, bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=bind; op=gate; target=ativacao.custo | action=<tipo>: custo p/ ativar esta habilidade. action:<tipo>+instant{} concede execução. |
| `activate` | 8 | classe-hab, traco | forma=key_value; op=grant_execution; target=efeitos.ativos | Ativa uma habilidade, opção ou definição referenciada. A identidade do efeito fica na referência, nunca em uma condição específica: activate:ability{frenesi_de_sangue, essencia:vampirismo}. |
| `add_mastery` | 6 | classe-hab, talento | forma=key_value; op=grant_proficiency; target=arma.maestria | Concede uma Maestria de Arma a um perfil (unarmed_strike.add_mastery:empurrar). Valor = slug de TB_OpcaoJogo[Maestria de Arma]. mastery{swap:<a>:<b>} troca a maestria de uma arma. |
| `add_property` | 131 | classe-hab, item-mundano, opcao, talento | forma=key_value; op=set_value; target=arma.propriedades | Concede propriedade de arma a um perfil (Armas Integradas → acuidade). Difere de define:weapon...add_property{}. |
| `add_to_set` | 1 | classe-hab | forma=key_value; op=add_to_set | Adiciona um valor a uma coleção nomeada do estado. Ex.: add_to_set:arma_de_monge(wielded). |
| `adv` | 328 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=grant_roll_mod | Vantagem numa rolagem. |
| `all_checks` | 0 | - | forma=key_value; op=add_modifier; target=pericias.bonus | Bônus numérico em TODOS os testes de habilidade (perícias). Sinônimo de ability_check:+ (que é roll-id). '(unless:proficient)' restringe às perícias sem proficiência (Bardo Pau Pra Toda Obra = +rounddown(pb/2)). |
| `all_saves` | 15 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=add_modifier; target=saves.bonus | Bônus numérico em TODOS os saves (Aura de Proteção: all_saves:+max(cha_mod,1); Magnum Opus: all_saves:+sintonizacao_ativa). |
| `allow_concentration` | 2 | classe-hab | forma=key_value; op=set_value; target=concentracao.max | Mantém concentração em N magias simultâneas (Ato Contínuo: allow_concentration:2). |
| `allow_reaction` | 2 | classe-hab | forma=key_value; op=set_value; target=reacoes.max | Eleva o teto de Reações (allow_reaction:2(per:trigger) — Reflexos Rápidos: 2 reações no mesmo gatilho). Análogo a allow_concentration. |
| `always_active` | 394 | antecedente, classe-hab, item-magico, opcao, talento, traco | forma=flag; op=gate | Passiva sempre ligada (sem action). |
| `any_bestiary` | 1 | magia | forma=reference | Referência dinâmica ao bestiário por filtros; usada em define{} quando uma escolha aceita qualquer criatura compatível, como qualquer Besta de ND 0 para familiar. |
| `aoe` | 191 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=block; op=emit_area | aoe{ point\|forma:tam, save{...}, dmg, on_success } — detonação pontual; resolve teste+efeito e acaba. |
| `apply` | 253 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=apply_condition; target=alvo | apply:<condição>(save:..., duração). |
| `apply_poison` | 1 | talento | forma=key_value; op=grant_execution | Aplica uma dose de veneno à arma/munição como parte de uma ação (Envenenador). |
| `area` | 10 | antecedente, classe-hab, traco | forma=key_value; op=emit_area; target=area.tamanho | Multiplicador/tamanho de área (aoe.area:*3). Campo de aoe, par de radius/point. |
| `at_will` | 643 | bestiario, classe-hab, item-magico, traco | forma=flag; op=add_modifier | Qualificador de cast{}: conjura À VONTADE (sem custo de recurso nem limite de usos). Atalho consagrado, mantido de propósito: equivale a cast{without{slot}} sem uses{}/resource_cost, mas o volume de uso e a clareza justificam a primitiva. |
| `atk` | 176 | classe-hab, item-magico, opcao, traco | forma=key_value; op=add_modifier; target=ataque.bonus | Bonus em jogadas de ataque concedido por item/efeito. Escopo pode refinar: weapon.atk:+1, spell.atk:+1, unarmed.atk:+1. |
| `atk_attr` | 2 | classe-hab, traco | forma=key_value; op=set_value; target=ataque.acerto.atributo | Atributo usado na rolagem de ATAQUE de um escopo (atk_attr:cha — Arma Mística usa Carisma no lugar de For/Des). Par exato do dmg_attr. Aprovado 2026_06_19. |
| `attack` | 317 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=grant_execution; target=ataque | Perfil/execução de ataque: attack:melee, attack:+X (bônus). |
| `attacks` | 33 | bestiario, classe-hab, opcao | forma=key_value; op=set_value; target=ataque.qtd | Nº de ataques na Ação de Ataque (attacks:=2; progressões attacks:={classlvl=...}). |
| `attr` | 41 | classe-hab, item-magico, talento, traco | forma=key_value; op=alter_attribute; target=atributos | attr:<attr>-score+N — altera valor de atributo. |
| `attr_max` | 19 | classe-hab, item-magico | forma=key_value; op=alter_attribute | Altera o teto do atributo. |
| `aura` | 140 | classe-hab, item-magico, opcao, talento, traco | forma=block; op=emit_area | aura{ radius, target:<allies\|enemies\|all>, effects{...} } — emanação contínua presa ao personagem. |
| `auto_result` | 2 | classe-hab, traco | forma=key_value; op=set_value; target=rolagem | Trata a próxima rolagem de d20 como 20/1 natural (Axioma de Thamior). Par de auto_save_success. |
| `auto_save_success` | 9 | classe-hab, item-magico, opcao, talento, traco | forma=flag; op=set_value; target=save.auto | Sucesso automático num teste de resistência (Manto das Raízes e Marés / Contatar o Patrono). |
| `avoid` | 0 | - | forma=key_value; op=gate | Modo de evitar um perigo/área sem rolar, por exemplo avoid:half_speed em estrepes ou rolamentos. |
| `break` | 0 | - | forma=block; op=grant_execution | Quebrar/arrebentar um objeto ou restrição: break{save{str, cd=20}}. |
| `breathe` | 8 | classe-hab, item-magico, opcao, traco | forma=key_value; op=set_value; target=respiracao | Respiração em ambiente especial (breathe:underwater — Presente do Oceano). Flag de ambiente, par de move:swim. Aprovado 2026_06_18. |
| `buff` | 18 | classe-hab, magia, opcao, talento, traco | forma=key_value; op=add_modifier | Bônus temporário (buff:max_hp:+5). |
| `ca` | 162 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=bind; op=set_value; target=ca | Sobrescreve CA (ca=10+dex_mod+con_mod). |
| `cast` | 2794 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block; op=cast_spell | Concede conjuração de uma magia: cast{spell:<slug>, ...} OU seleção dinâmica cast{spell:pick{lista:<classe>, nivel<=N}} (Intervenção Divina, Arcana Mística). |
| `cast_from` | 1 | classe-hab | forma=key_value; op=set_value; target=conjuracao.origem | Suas magias PARTEM de um ponto/ilusão referenciado, usando seus próprios sentidos (cast_from:ilusao(use:own_senses) — Invocar Duplicidade). Relocaliza a origem da conjuração de forma passiva (≠ origem: num cast{} pontual). Aprovado 2026_06_18. |
| `cast_level` | 12 | classe-hab, item-magico, traco | forma=key_value; op=cast_spell | Conjura a magia num NÍVEL/ciclo fixo (cast_level:5). Absorve cast_as_cycle. Difere de upcast (que escala por espaço gasto). |
| `cd` | 352 | antecedente, bestiario, classe-hab, item-magico, item-mundano, opcao, talento, traco | forma=bind; op=set_value; target=save.cd | Classe de Dificuldade do teste/efeito (cd=8+pb+con_mod). NÃO é duração. |
| `charges` | 225 | item-magico, item-mundano | forma=key_value; op=meta | Metadado de item com cargas: charges:<N>(reset:dawn\|daily\|none). Para itens com contador proprio na ficha. |
| `check` | 107 | antecedente, classe-hab, item-magico, magia, opcao, talento, traco | forma=block | Teste de perícia/atributo: check{<pericia>} ou check{<attr>}. Usado em adv:check{furtividade}, trigger=check{...}, contest. Roll_id base de <attr>-check. |
| `check_attr` | 23 | antecedente, classe-hab, talento, traco | forma=key_value; op=set_value; target=pericia.atributo | Troca o ATRIBUTO de uma perícia (check_attr:persuasao:=forca = Persuasão com Força; Mente Afiada usa INT). Aprovado 2026_06_17. |
| `check_bonus` | 56 | antecedente, classe-hab, item-magico, magia, talento, traco | forma=key_value; op=add_modifier; target=pericia.bonus | Soma fixa a UM teste de perícia nomeado (check_bonus:religiao=max(wis_mod,1)). Aprovado 2026_06_17. |
| `check_swap` | 1 | classe-hab | forma=key_value; op=set_value; target=pericia.swap | Rola uma perícia no lugar de outra num teste (check_swap:persuasao=religiao(ability:wis) — Autoridade Sagrada). ≠ check_attr (que troca só o ATRIBUTO). Aprovado 2026_06_18. |
| `cleanse` | 64 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=apply_condition; target=self | Remove condição (inverso de apply). cleanse:pick:{amedrontado \| enfeiticado \| envenenado}; cleanse:magia(qtd:1) = encerra efeito de magia; cleanse:reaction / cleanse:concentration = remove a Reação/Concentração de inimigos na área (capstones). Aprovado 2026_06_17. |
| `color_vision` | 2 | opcao, traco | forma=flag; op=emit_area; target=sentidos | Enxerga em CORES na escuridão (não em tons de cinza). Qualificador de sense:darkvision. |
| `command` | 4 | classe-hab | forma=key_value; op=grant_execution | Comanda um companheiro/objeto invocado (command:mao_magica, command:companion). Família de summon. |
| `concentration_check` | 4 | classe-hab, opcao, traco | forma=key_value; op=grant_roll_mod | Modificador no teste de Concentração (concentration_check:adv\|dadv). |
| `cond_immune` | 63 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_to_set; target=imunidades_condicao | - |
| `cone` | 26 | classe-hab, item-magico, magia, traco | forma=key_value | Forma de área. |
| `consumable` | 369 | item-magico, item-mundano | forma=flag; op=meta | Marca item consumivel: pocao, pergaminho, municao, veneno, explosivo ou item gasto/descartado no uso. |
| `consume` | 8 | bestiario, classe-hab, traco | forma=key_value; op=grant_execution | Consome um item/consumível como parte do efeito (consume:item_alquimico — Sifão de Arma). |
| `contest` | 4 | classe-hab, opcao | forma=block | Teste CONTESTADO (ex.: Agarrar: contest{atletismo vs atletismo\|acrobacia}). Difere de save{} (CD fixa). roll_add some o dado de recurso ao teste. |
| `convert_dmg_type` | 27 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=set_value; target=ataque.dano.tipo | Converte o TIPO de TODO o dano causado nesta ação/turno (Alma Radiante → radiante). 'weapon_type' = mesmo tipo da arma usada (dinâmico). Difere de dmg_type (perfil de arma). |
| `count_as` | 7 | traco | forma=key_value; op=set_value | Tratado como outra raça/tipo de criatura p/ pré_requisitos (count_as:anao(for:prereq) — Cultura Adotada) ou percepção (count_as:humanoide(for:detection) — Eremita Diurno). Absorve detect_as. |
| `cover` | 19 | classe-hab, item-magico, opcao, talento | forma=key_value; op=set_value; target=cobertura | Concede cobertura (meia/três_quartos/total), geralmente em effects de aura. |
| `create` | 7 | classe-hab, opcao, talento, traco | forma=key_value; op=grant_execution | Cria um item consumível temporário (Chef: create:petisco(qtd:pb)). qtd:<n> = instâncias. |
| `creature_type` | 32 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=set_value; target=corpo.tipo | Define/sobrescreve o tipo de criatura do personagem (creature_type:=[humanoide, construto] — Mestre Aprimorado). Aprovado 2026_06_18. |
| `crit` | 10 | classe-hab, item-magico, talento, traco | forma=flag; op=set_value; target=ataque.crit | crit:auto = este ataque é Acerto Crítico automático (Momento Perfeito, Angústia Mental). |
| `crit_dmg` | 5 | classe-hab, talento, traco | forma=bind; op=add_damage; target=ataque.crit | Dado extra no crítico. Use escopo (weapon.crit_dmg=+1d10). |
| `crit_range` | 15 | classe-hab, opcao | forma=key_value; op=add_modifier; target=ataque.crit_range | Amplia margem de crítico (str_atk.crit_range:+1). |
| `cube` | 17 | classe-hab, magia, opcao, traco | forma=key_value | - |
| `cylinder` | 5 | magia, traco | forma=key_value | Forma de área (cilindro). |
| `dadv` | 140 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=grant_roll_mod | Desvantagem numa rolagem. |
| `dash` | 30 | classe-hab, opcao, talento, traco | forma=flag; op=grant_execution | Execução: Disparada. |
| `death_save` | 10 | item-magico, talento, traco | forma=key_value; op=grant_roll_mod | Teste contra a Morte: roll_id p/ adv/dadv (adv:death_save) e evento (trigger=death_save). |
| `define` | 145 | antecedente, bestiario, classe-hab, magia, opcao, talento, traco | forma=block; op=define; target=definicoes | Registra método/tabela/lista/arma local (ver 'definicoes_inline'). |
| `destroy` | 7 | bestiario, classe-hab | forma=key_value; op=grant_execution | Destrói alvo/objeto. |
| `detect` | 29 | antecedente, classe-hab, item-magico, opcao, traco | forma=key_value; op=emit_area; target=sentidos | DETECTA algo do mundo (alvo em PT): detect:{creature_type:[celestial, morto_vivo]}, detect:magia, detect:sitio_sagrado, detect:plano_etereo, detect:invisivel. Pode mapear p/ cast{} de magia equivalente. NÃO existe detect:mentira — 'saber se alguém mente' é regra de flavor, não codável. |
| `dice` | 71 | antecedente, bestiario, classe-hab, item-magico, talento, traco | forma=key_value; op=roll_table | Dados de uma rolagem/tabela (dice:1d12, dice:2d12). |
| `die_min` | 6 | opcao, talento, traco | forma=key_value; op=set_value | Piso por DADO (trata <=N como o piso; Armas Grandes 1_2→3). die:-1_step = reduz a categoria do dado (Estocada). |
| `die_step` | 0 | - | forma=key_value; op=set_value | Altera a categoria do dado em ±N passos (die_step:-1 = Estocada reduz; die_step:+1 = aumenta). Par de die_min (piso). |
| `difficult_terrain` | 47 | classe-hab, item-magico, opcao, talento, traco | forma=flag; op=emit_area; target=terreno | Torna a área terreno difícil para os alvos (effects de aura/aoe). |
| `disengage` | 25 | classe-hab, opcao, talento, traco | forma=flag; op=grant_execution | Execução: Desengajar. |
| `dispersed_by` | 1 | item-mundano | forma=key_value; op=gate | Condição ambiental que encerra/dispersa uma área: dispersed_by:strong_wind. |
| `dmg` | 985 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=add_damage; target=ataque.dano | Dano (verbo E valor; nunca 'damage'). dmg:+1d6, dmg:8d6(fogo), dmg:+(roundup(classlvl/2)). (auto) = sem rolagem. Tipo escolhido inline: dmg:+1d8(pick:{raio \| fogo \| frio \| trovejante}). without{crit_mult} marca dano não multiplicado no crítico. |
| `dmg_attr` | 3 | classe-hab, traco | forma=key_value; op=set_value; target=ataque.dano.atributo | Atributo usado no dano de um escopo (natural.dmg_attr:=wis). Campo de ataque, par de check_attr/save_attr/jump_attr. |
| `dmg_reduction` | 40 | classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_modifier; target=dano_recebido | Reduz dano recebido; rolável/por reação (Desviar Ataques: dmg_reduction:1d10+dex_mod+classlvl); 'half' = metade arredondando p/ baixo (Esquiva Instintiva); escopo de fonte take_damage{fall} (Queda Lenta). |
| `dmg_type` | 33 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=set_value; target=ataque.dano.tipo | Define o tipo de dano. |
| `dodge` | 11 | classe-hab, opcao, traco | forma=flag; op=grant_execution | Execução: ação Esquivar (ataques contra você com Desvantagem; saves de Des com Vantagem). |
| `downgrade_crit` | 2 | classe-hab, item-magico | forma=flag; op=set_value; target=defesa.crit | Transforma um crítico recebido em acerto comum (anula o crítico inteiro; mais forte que without{crit_mult}). |
| `draw` | 9 | classe-hab, talento, traco | forma=key_value; op=roll_table; target=tabela.resultados | Compra ou sorteia N resultados de uma tabela ou baralho definido. Ex.: draw:3(from:ability{arcanos_do_veu, classe:bardo}, unique). |
| `drop_held_item` | 4 | classe-hab, opcao | forma=flag; op=apply_condition; target=alvo | Força o alvo a soltar o que segura (Exigência da Ordem). |
| `effects` | 115 | classe-hab, item-magico, opcao, talento, traco | forma=block | Bloco de efeitos aplicados pela área/aura. |
| `end` | 35 | classe-hab, opcao, traco | forma=key_value; op=grant_execution; target=efeitos.ativos | Encerra uma instância ativa referenciada: end:ability{receptaculo_do_genio, classe:mistico} ou end:defined{mutagenico_preparado}(pick:1). |
| `enhance` | 43 | classe-hab, opcao, traco | forma=key_value; op=add_modifier | Aprimora algo existente. |
| `equip` | 8 | classe-hab, talento, traco | forma=key_value; op=grant_execution | Manipula equipamento sem ação extra: equip:draw (sacar) \| equip:stow (guardar) \| equip:reload (recarregar). Para ignorar Carregar use without{loading}. |
| `equiped` | 57 | antecedente, classe-hab, item-magico, opcao, talento, traco | forma=block; op=gate | Restrição/requisito por equipamento equipado. |
| `escape` | 5 | classe-hab, opcao | forma=block; op=grant_execution | Escapar de contenção, armadilha, rede ou algemas: escape{action=action, save{str, cd=13}}. |
| `exclude` | 6 | classe-hab, opcao, traco | forma=key_value; op=add_to_set; target=alvo.exclusoes | Remove seletores do conjunto de alvos de um efeito ou área. Ex.: exclude:creature{self, chosen, qtd:max(int_mod,wis_mod)}. |
| `expertise` | 21 | classe-hab, opcao, talento, traco | forma=key_value; op=grant_proficiency | Especialização (dobro do PB). CONSUMIDO no derive (modo estático): expertise:<perícia> em segmento passivo marca proficiente+expertise na perícia (implica proficiência). Escolha de expertise entre proficientes = pick:pericia_expertise (kind no PICK_REGISTRY, readback no derive). expertise:tool{}/ferramentas ficam inertes (a ficha não deriva teste de ferramenta). |
| `extinguish` | 1 | talento | forma=key_value; op=emit_area; target=fogo_na_area | Apaga chamas/fogo NÃO mágico na área (Brumas Ofuscantes: extinguish:fire(nonmagical, in_aura)). Não cria escuridão (use 'light:none' p/ isso). Aprovado 2026_06_26. |
| `extra_d20` | 2 | talento, traco | forma=key_value; op=grant_roll_mod | Rola um d20 ADICIONAL e mantém o melhor (Precisão/Olho Crítico). Difere de adv (2 dados): empilha um 3º d20. |
| `focus` | 14 | classe-hab, talento | forma=key_value; op=set_value; target=conjuracao.foco | Define o foco de conjuração de uma magia concedida por talento (focus:baralho \| focus:wielded \| focus:simbolo_sagrado). |
| `force` | 4 | classe-hab, traco | forma=key_value; op=grant_execution; target=alvo | Compele o alvo a realizar uma ação (force:attack(profile:..., target:nearest_living) — Frenesi de Sangue). Controle de ação forçada. |
| `forrageio` | 2 | antecedente | forma=key_value | Encontrar recursos naturais na terra: forrageio:comida_e_agua(target:6) — para si e até N pessoas por dia, se houver fonte natural. Aprovado 2026_06_19. |
| `grant` | 84 | classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=grant_execution | Concede algo ao alvo. grant:extra_action = uma ação completa extra no turno (Surto de Ação; não cabe nos 4 custos nem em execução). CONCESSÕES FIXAS consumidas no derive: grant:opcao:<tipo>:<slug>(extra, always_prepared) e grant:opcao{<tipo>: [<slugs>], fora_do_limite} materializam uma opção fora do painel de pick; grant:talento{<slug>, without{asi}} concede os benefícios de um talento sem o incremento de atributo. O resto segue runtime/VTT. |
| `half_components` | 1 | traco | forma=flag; op=override | Conjura com METADE dos componentes materiais (Última Rodada). |
| `heal` | 151 | antecedente, bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=heal; target=pv | heal:2d8+spell_mod. heal:max = maximiza os dados de cura (Cura Suprema). Idem dmg:max. |
| `help` | 12 | classe-hab, talento, traco | forma=flag; op=grant_execution | Execução: ação Ajudar (sempre 'help' em inglês, nunca 'ajuda'). |
| `hide` | 16 | classe-hab, opcao, talento, traco | forma=flag; op=grant_execution | Execução: Esconder_se (teste de Furtividade). Aprovado 2026_06_17. |
| `hp` | 55 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=set_value; target=pv.atual | hp:=1 (Fôlego Furioso). |
| `ignites` | 0 | - | forma=key_value; op=emit_area | Indica que o efeito incendeia certos alvos/materiais: ignites:flammable. |
| `ignore` | 59 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=set_value | Ignora uma propriedade ou regra durante uma interação, sem removê-la do alvo. Exemplos: ignore:resist, ignore:cover, ignore:difficult_terrain. Pode ser qualificado por escopo: weapon.ignore:resist ou move.ignore:difficult_terrain. |
| `imbue` | 6 | classe-hab, talento, traco | forma=key_value; op=grant_execution | Imbui um objeto tocado com um efeito até o fim da duração (Portador da Luz: imbue:object(sunlight)). |
| `immune` | 41 | bestiario, classe-hab, item-magico, traco | forma=key_value; op=add_to_set; target=imunidades | - |
| `immune_ability` | 10 | classe-hab, talento, traco | forma=block; op=apply_condition; target=alvo | O alvo fica imune a ESTA habilidade por uma duração (Assecla: immune_ability(duration:24h)). |
| `immune_effect` | 19 | classe-hab, magia, traco | forma=key_value; op=add_to_set; target=imunidades_efeito | immune_effect:<efeito>(requires:source{...}) — imune a um EFEITO que nao e condicao catalogada (ex.: empurrar/derrubar por meios nao magicos). Investidura da Pedra. Aprovado 2026_06_22. |
| `in_aura` | 26 | classe-hab, talento, traco | forma=flag | Condição: estar dentro da aura. |
| `in_light` | 6 | classe-hab, traco | forma=flag | Condição: estar iluminado. |
| `initiative` | 52 | classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_modifier; target=iniciativa | Soma um modificador à iniciativa. Ex.: initiative:+pb. Vantagem ou Desvantagem continuam em adv:initiative e dadv:initiative. |
| `instant` | 1110 | antecedente, bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=block; op=gate | Acontece e acaba; corpo é bloco de efeitos. |
| `jump` | 6 | classe-hab, talento, traco | forma=key_value; op=add_modifier; target=movimento.salto | - |
| `jump_attr` | 1 | classe-hab | forma=key_value; op=set_value; target=movimento.salto.atributo | Atributo do salto (jump_attr:=dex). |
| `keep` | 38 | classe-hab, magia, talento, traco | forma=key_value; op=roll_table | Modo de aproveitamento dos dados rolados. |
| `light` | 42 | bestiario, classe-hab, opcao, talento, traco | forma=key_value; op=emit_area; target=iluminacao | Iluminação (≠ propriedade de arma 'leve'). light:none = escuridão mágica (suprime luz). |
| `limit` | 10 | antecedente, classe-hab, opcao, talento, traco | forma=key_value; op=set_value; target=efeito.teto | Teto de instâncias/contagem simultâneas de um efeito (limit:1 — Marca da Alma, Voto Compartilhado). Análogo a allow_concentration. Cobre max_active. Aprovado 2026_06_18. |
| `line` | 24 | classe-hab, magia, opcao, traco | forma=key_value | - |
| `log_castable` | 1 | magia | forma=flag; op=meta | Termo consagrado: marca magia conjurável FORA de jogo (pelo log da ficha) para efeito real duradouro, tipicamente por ter tempo de conjuração longo e/ou componentes materiais e criar um estado persistente. Ex.: Encontrar Familiar (familiar por tempo indeterminado), Simulacro, Glifo de Vigilância, Aura Mágica (permanente após 30 dias). NÃO depreciar. |
| `maestrias` | 54 | item-mundano | forma=block; op=meta | Lista de maestrias de arma disponíveis no item mundano. O valor referencia slugs de TB_OpcaoJogo quando houver correspondência. |
| `marcha_forcada` | 1 | antecedente | forma=key_value | Ritmo de viagem estendido (não é o move: de combate): marcha_forcada(max:16h) — marcha o dobro do tempo antes do efeito de marcha forçada. Aprovado 2026_06_19. |
| `mark` | 37 | bestiario, classe-hab, opcao, traco | forma=block; op=mark | Contador em alvos (ver primitivas de área/marca). |
| `max_cr` | 1 | opcao | forma=key_value; op=meta; target=filtro.max_cr | Filtro de Nível de Desafio máximo (max_cr:N / cr<=N) para formas assumíveis / criaturas invocáveis (Forma Selvagem, metamorfose, invocações). Inerte na ficha estática (efeito de seleção/combate — ficha-de-log). |
| `max_hp_reduction` | 5 | classe-hab, talento | forma=key_value; op=set_value; target=pv.maximo | Reduz o PV MÁXIMO (Hemomancia): max_hp_reduction:+<f>(reset:long_rest). Gasta vitalidade até o descanso. Aprovado 2026_06_18. |
| `min` | 39 | antecedente, classe-hab, item-magico, item-mundano, talento, traco | forma=key_value; op=grant_roll_mod | Piso de resultado (min:str_check=str_score). |
| `modifiers` | 419 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block | Bloco de modificadores dentro de cast{}/outros. |
| `modify` | 200 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=override | modify:<entidade_ref>.<prop>{...} — override genérico numa entidade referenciada. |
| `move` | 160 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_to_set; target=movimento.modos | Modo de movimento (escalar:eq/nadar:eq/fly:eq = igual ao deslocamento). wall = sobe superfícies verticais; liquid = anda sobre líquidos (Movimento Acrobático — aprovado 2026_06_17). |
| `move_through` | 12 | classe-hab, traco | forma=flag; op=grant_execution | Atravessa espaço de criaturas. |
| `movement_cost` | 8 | classe-hab, talento, traco | forma=key_value; op=set_value; target=movimento.custo | Sobrescreve o custo de uma manobra de movimento: movement_cost:stand_up=5ft (Formação Bastiônica), movement_cost:mount=0 (Escudeiro). |
| `need` | 5 | classe-hab, traco | forma=key_value; op=set_property; target=corpo.necessidades | Declara necessidades fisiológicas de forma genérica. Exemplos: need:air=false, need:food=false, need:water=false, need:sleep=false. Não crie verbos no_breathe, no_eat ou no_sleep. |
| `negate_effect` | 4 | talento, traco | forma=key_value; op=gate | Previne/anula um efeito iminente sobre um aliado protegido (Guarda de Formação). Par defensivo de apply. |
| `next_melee_dmg` | 1 | opcao | forma=key_value; op=add_modifier; target=alvo.proximo_ataque.dano | Debuff no dano do PRÓXIMO ataque corpo a corpo do alvo (next_melee_dmg:-ability_mod — maestria Debilitar/Weaken). Aprovado 2026_06_18. |
| `not` | 52 | classe-hab, opcao, talento, traco | forma=block; op=predicate_not; target=predicados | Negação booleana de um predicado, válida dentro de requires{}, restriction{}, if(), unless() e filtros. Exemplos: requires{not{condition{incapacitado, target:self}}}, restriction{not{equipped{mascara_da_piedade}}}. Não produz efeito e não substitui restricts{}, suppress{} ou immune_effect:. |
| `object_hp` | 0 | - | forma=key_value; op=set_value | PV ou durabilidade de um objeto mundano quando isso importa mecanicamente: object_hp:2. |
| `obscured` | 12 | classe-hab, item-mundano, opcao, talento, traco | forma=key_value; op=emit_area; target=visao | Cria área leve/intensamente OBSCURECIDA (obscured:heavy\|light). Eixo de visão do 5e (afeta Percepção/ataques) DISTINTO de light:none (escuridão mágica). Também buff passivo de Furtividade (Manto da Caçada). Aprovado 2026_06_18. |
| `on` | 160 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=gate | on:<evento> -> <efeito>. Evento da própria duração (ex.: on:end). |
| `on_fail` | 181 | classe-hab, item-magico, item-mundano, opcao, talento, traco | forma=key_value; op=set_value; target=save.on_fail | Resultado na falha (contraparte de on_success). Evasão = source{aoe}.save{dex}.on_success:=none, on_fail:=half (sem verbo 'evasion' — decisão 2026_06_17). |
| `on_success` | 295 | classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=set_value; target=save.on_success | Resultado no sucesso do teste (metade/nada). |
| `opcao` | 46 | classe-hab, opcao, talento | forma=reference | Referência a tipo de opção de jogo. |
| `pick` | 488 | antecedente, bestiario, classe, classe-hab, essencia, item-magico, magia, opcao, talento, traco | forma=key_value; op=pick | Abre N escolhas (ver 'escolhas'). |
| `play` | 2 | classe-hab | forma=key_value; op=grant_execution; target=execucao.opcao_preparada | Executa e consome uma opcao previamente preparada. Ex.: play:prepared_arcano(target:creature(range:30ft), discard_after). |
| `point` | 21 | classe-hab, opcao, traco | forma=key_value | - |
| `prof` | 153 | antecedente, classe, classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=grant_proficiency; target=proficiencias | Concede proficiência. Use prof:<categoria>{<valor>} p/ evitar duplo dois_pontos. |
| `pull` | 17 | classe-hab, opcao, talento, traco | forma=key_value; op=grant_execution; target=alvo | Movimento FORÇADO: puxa o alvo <ft> (pull:10ft). Aprovado 2026_06_17. |
| `push` | 48 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=grant_execution; target=alvo | Movimento FORÇADO: empurra o alvo <ft> (push:10ft; from:<sel> opcional). Aprovado 2026_06_17. |
| `radius` | 236 | bestiario, classe-hab, item-magico, item-mundano, opcao, talento, traco | forma=key_value | - |
| `range` | 454 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value | Alcance. |
| `reach` | 12 | classe-hab, opcao, talento, traco | forma=key_value; op=add_modifier; target=corpo.alcance | - |
| `read` | 1 | classe-hab | forma=key_value; op=grant_execution | Ler/compreender escrita (read:any_language). Par utilitário de speak:. |
| `redirect_damage` | 12 | classe-hab, item-magico, talento, traco | forma=key_value; op=set_value; target=dano_recebido | Sofre no lugar de outra criatura / redireciona dano (Aura do Guardião). Valor via damage_taken. |
| `redirect_heal` | 3 | classe-hab, opcao | forma=key_value; op=heal | Realoca a cura (ex.: rouba a cura de um inimigo — Sopro de Nascira). |
| `redirect_save` | 1 | classe-hab | forma=key_value; op=set_value | O alvo faz o teste no lugar de outra criatura / redireciona um save (família redirect_*). |
| `reduce_forced_movement` | 2 | talento, traco | forma=key_value; op=add_modifier; target=movimento.forcado | Reduz os pés de movimento FORÇADO que você sofre (reduce_forced_movement:+pb). |
| `reload` | 5 | classe-hab, item-mundano, talento | forma=flag; op=grant_execution | Recarrega arma de munição/recarga (Besteiro). Atalho de equip:reload. |
| `repeat_save` | 24 | classe-hab, item-magico, item-mundano, opcao, traco | forma=key_value; op=apply_condition; target=save.repeat | Save_ends: o alvo repete o teste no evento dado e encerra o efeito em sucesso (repeat_save:turn_end). |
| `repeat_turn` | 1 | classe-hab | forma=key_value; op=grant_execution | Concede um TURNO inteiro extra a outra criatura, fora da iniciativa (Paradoxo da Repetição). Manipulação de ordem de turno — ≠ grant:extra_action (1 ação no próprio turno). Aprovado 2026_06_18. |
| `repeat_while` | 1 | classe-hab | forma=key_value; op=gate | Repete a execução anterior ENQUANTO a condição valer (attack:weapon(...)(repeat_while:resource{X}>0) — Golpes Encadeados). Construto de laço. Aprovado 2026_06_18. |
| `repeatable` | 6 | opcao, talento | forma=flag; op=pick | A opção/escolha pode ser tomada mais de uma vez (Aprendizado dos Antigos). |
| `replace_attack` | 11 | classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=grant_execution | Substitui um dos ataques da Ação de Ataque por outra execução (truque — Segundo Ataque Mágico). |
| `replace_d20` | 7 | classe-hab, item-magico, talento | forma=key_value; op=set_value; target=rolagem | Substitui o d20 de um teste por valor fixo (replace_d20:classlvl — Cena é Corpo). Difere de min: (piso). |
| `replace_save` | 1 | traco | forma=key_value; op=set_value; target=save.atributo_defensivo | Troca o ATRIBUTO do save DEFENSIVO exigido (replace_save:con(instead_of:dex) — Campeão das Cúpulas). Par de save_attr (que você impõe) e check_swap (perícia). |
| `requires` | 745 | antecedente, classe-hab, item-magico, item-mundano, opcao, talento, traco | forma=key_value; op=gate | Condição POSITIVA exigida (inverso de restriction). Relações usam referência genérica: requires:condition{amedrontado, source:self}; nunca predicados específicos *_by_self, *_por_self ou *_self. |
| `reroll` | 33 | classe-hab, magia, opcao, talento, traco | forma=flag\|block; op=grant_roll_mod | Rola de novo (em table{} = rola na mesma tabela). |
| `reset` | 1481 | antecedente, bestiario, classe-hab, item-magico, item-mundano, opcao, talento, traco | forma=key_value; op=resource | Quando o recurso recupera. level_up = ao subir de nível (retraining); 2d4_long_rest = após Nº aleatório de descansos longos (Intervenção Divina Maior). |
| `resist` | 243 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_to_set; target=resistencias | resist:fogo, resist:source{magical_effect}, resist:last_damage_type. |
| `resource` | 194 | classe-hab, opcao, talento, traco | forma=reference; op=resource; target=recursos | REFERENCIA um pool de recurso. REGRA (2026_06_18): SÓ vão na TB_RecursoClasse pools que ESCALAM por nível de classe (Fúrias 2→6, pontos_de_ki=nível — via valores_json). Pools de FÓRMULA (max=pb/mod/2*pb) ou FIXOS (teto 3) são INTERNOS: declarados via define{<slug>: max:<fórmula>, reset:..., [die:...]} na habilidade_fonte (NÃO na tabela) e referenciados normalmente por resource{<slug>}/resource_cost:<slug>. O uso da própria habilidade também é um pool (resource_cost:<nome_da_habilidade>). TbRecursoclasse.tipo define o papel no builder: table_only (informativo), consumable (rastreador de usos) ou choice (quantidade de escolhas nao consumidas). |
| `resource_cost` | 610 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=key_value; op=resource | Gasta uso(s). resource_cost:furias (=1); quantidade: resource_cost:<rec>:<N> (resource_cost:pontos_de_ki:2); faixa fechada :1..3 ou aberta :1..all (gasta quanto quiser; Ímpetos Arcanos); custo alternativo {a\|b}. Em recurso table_only usado como orçamento local (ex.: dados_de_furtividade), o custo reduz a quantidade da ativação atual e não cria tracker persistente. |
| `resource_restore` | 98 | classe-hab, item-magico, talento, traco | forma=key_value; op=resource | Restaura recurso. =all; quantidade: resource_restore:<rec>:<N>; com teto de nível: resource_restore:spell_slot:1(max_nivel:roundup(pb/2)) (Recorrer ao Poder Divino, Recuperação Arcana). |
| `restriction` | 126 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block; op=gate | Condição bloqueadora do escopo atual: se a condição for verdadeira, este efeito/habilidade não pode ser usado ou não se aplica. No topo bloqueia toda a habilidade; dentro de um bloco bloqueia só aquele bloco. Ex.: restriction{inconsciente}; always_active{restriction{equiped{armor}}, ca=10+dex_mod+con_mod}. |
| `restricts` | 35 | classe-hab, opcao, traco | forma=block; op=restrict | Proibição imposta pelo efeito ativo ao personagem/alvo. Use quando a habilidade restringe uma ação enquanto está ativa. Ex.: while_active{restricts{spellcasting, concentration}} em Fúria. |
| `ritual` | 17 | classe-hab, magia, opcao, talento, traco | forma=flag; op=add_modifier | - |
| `roll` | 92 | antecedente, bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block; op=roll_table | Rolagem genérica (ver functions.roll). |
| `roll_add` | 58 | classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=add_modifier; target=rolagem | Soma a uma rolagem disparada por gatilho (Momento de Ajuste: roll_add:+2*spent; Lampejo de Gênio: roll_add:+int_mod a teste de aliado). |
| `same_cd` | 22 | classe-hab, opcao, talento, traco | forma=flag; op=set_value | Usa a mesma CD de referência. |
| `save` | 618 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=block | Teste de resistência (ver functions.save). |
| `save_attr` | 1 | classe-hab | forma=key_value; op=set_value; target=save.atributo | Atributo do teste de resistência que o efeito impõe (save_attr:=int). |
| `save_prof` | 13 | classe-hab, talento, traco | forma=key_value; op=grant_proficiency; target=saves | - |
| `search` | 5 | classe-hab, talento | forma=flag; op=grant_execution | Execução: ação Procurar. |
| `sense` | 145 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=emit_area; target=sentidos | Sentido/visão que a criatura POSSUI. darkvision cobre escuridão comum; devilsight é declarado separadamente quando também atravessa escuridão mágica. Para detectar algo do mundo use detect:. |
| `set` | 17 | traco | forma=bind; op=set_value; target=variaveis | Atribui uma variável de ESCOLHA/estado do personagem (set:descendencia=wyvern). Base das transformações/escolhas de essência; referenciada depois por requires:<var>=<valor> e match(<var>){...}. |
| `share_senses` | 7 | bestiario, classe-hab, opcao | forma=key_value; op=grant_execution; target=sentidos | Percebe pelos sentidos de um vínculo/familiar. |
| `sintonizacao` | 5 | classe-hab, item-magico | forma=key_value; op=alter_attribute; target=sintonizacao | Itens mágicos: o personagem sintoniza até 3 (padrão); item só tem efeito sintonizado; alguns exigem pré_req (raça/classe/conjurador — fica no item). attr_max:sintonizacao=N eleva o teto (Maestria em Itens Mágicos). |
| `size` | 41 | bestiario, classe-hab, opcao, talento, traco | forma=key_value; op=set_value; target=corpo.tamanho | - |
| `speak` | 15 | antecedente, classe-hab, talento, traco | forma=key_value; op=grant_execution | Falar com tipo de criatura. |
| `speed` | 144 | bestiario, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | forma=key_value; op=add_modifier; target=movimento.deslocamento | speed:+X. |
| `spell` | 2980 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=reference | Referência a magia (references.spell). |
| `spell_mod` | 191 | bestiario, classe-hab, magia, talento, traco | forma=flag | Variável: modificador de conjuração resolvido (substitui o uso de 'ability:' solto fora de spellcasting{}). Em casters de atributo escolhível usa o atributo definido em spellcasting{ability:int\|wis}. |
| `spell_selection` | 223 | classe-hab, talento, traco | forma=key_value; op=pick | Adiciona magia escolhida de uma lista; 'extra, fora_do_limite' = não conta no total; 'always_prepared' = sempre preparada (Montaria Heróica); 'qtd:<formula>' = N preparadas por fórmula. |
| `spellcasting` | 34 | classe, classe-hab, talento, traco | forma=block; op=declare_caster | Declara a conjuração da classe. slots:full\|half\|third\|pact(resource:<slug>) (pact = caster por pontos, recupera em descanso curto — Místico). ability:<attr> (ou int\|wis se escolhível). Ver 'tags_de_classe' e vocabulario §16. |
| `sphere` | 48 | classe-hab, item-magico, magia, opcao, traco | forma=key_value | - |
| `split_damage` | 2 | opcao, talento | forma=key_value; op=add_damage | Divide o dano rolado entre múltiplos alvos (split_damage:targets:N). |
| `spreads_around_corners` | 0 | - | forma=flag; op=emit_area | Área se propaga por esquinas/cantos, como explosões de pólvora. |
| `stabilize` | 3 | item-mundano, talento, traco | forma=flag; op=heal; target=alvo | Estabiliza uma criatura a 0 PV (Kit de Curandeiro/Medicina). |
| `study` | 2 | talento | forma=flag; op=grant_execution | Execução: ação Estudar (2024). Mente Afiada a torna ação bônus. |
| `summon` | 71 | antecedente, bestiario, classe-hab, item-magico, magia, traco | forma=key_value; op=summon | Invoca criatura(s) do bestiário (summon:bestiary{<slug>}; :N p/ quantidade). Statblock vive no bestiário; companheiros que escalam recebem scaling do invocador. Aprovado 2026_06_17. |
| `summon_hp` | 1 | classe-hab | forma=key_value; op=summon | Parâmetro de PV da criatura invocada (summon_hp:half). Scaling do summon (statblock vive no bestiário). |
| `sunlight` | 4 | talento, traco | forma=flag; op=emit_area; target=iluminacao | A luz produzida conta como LUZ DO SOL (relevante p/ mortos_vivos/vampiros). Qualificador de light:/imbue:. |
| `suppress` | 62 | classe-hab, essencia, item-magico, opcao, talento, traco | forma=block_or_key_value; op=suppress; target=efeitos.suprimidos | Desativa um efeito, modificador ou regra que normalmente estaria ativo, sem proibir a ação que o originaria. Exemplos: suppress{adv:attack{vs:self}}, suppress{condition{inconsciente}, trigger:hp=0}, suppress{penalty:passive_perception}. Não use without{} para esta semântica. |
| `sustain` | 9 | classe-hab, opcao | forma=key_value; op=grant_execution; target=execucao.sustentacao | Mantém um efeito ativo sem reiniciá-lo. Ex.: sustain:presentation(without{action}) ou sustain:concentration. O custo e as condições ficam nos argumentos. |
| `swap` | 44 | classe-hab, opcao, talento, traco | forma=key_value | Marca uma ESCOLHA (pick:) como RE_ESCOLHÍVEL no evento dado, SEM mudar de nível. Ex.: estilo de luta do Caçador trocável em descanso longo = pick:opcao:estilo_de_luta:1(swap:long_rest); magia CONHECIDA (não preparada) trocável ao subir de nível = pick:spell:N(swap:level_up). Metadado lido pela mecânica de level_up/edição da ficha — só use onde o texto da habilidade disser explicitamente que pode trocar. |
| `swap_initiative` | 3 | classe-hab, talento | forma=key_value; op=grant_execution | Troca seu resultado de iniciativa com o de um aliado voluntário (Alerta). swap_initiative:ally(willing). |
| `target` | 805 | antecedente, classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value | - |
| `targets` | 78 | classe-hab, magia, opcao, talento, traco | forma=key_value | Nº de alvos/dardos. |
| `telepathy` | 21 | bestiario, classe-hab, item-magico, talento, traco | forma=key_value; op=grant_execution; target=comunicacao | Comunicação telepática com um vínculo (telepathy:bound(range:same_plane)). |
| `teleport` | 73 | classe-hab, item-magico, magia, opcao, talento, traco | forma=key_value; op=grant_execution; target=movimento | - |
| `temp_hp` | 91 | classe-hab, magia, opcao, talento, traco | forma=key_value; op=heal; target=pv_temporario | temp_hp:+(con_mod * marks). |
| `toggle` | 8 | talento, traco | forma=key_value; op=set_value | Alterna entre dois estados mutuamente exclusivos (toggle:ofensivo\|defensivo; toggle:mente_aberta\|mente_fechada). Forma canônica para marcar uma habilidade LIGÁVEL/DESLIGÁVEL pelo jogador quando os dois estados são simplesmente ligado/desligado (sem nome próprio): toggle:on\|off, como cláusula-irmã dentro do while_active{} cujos efeitos ela ativa/desativa. Puro marcador — SEM comportamento no motor atual (home/tag_engine só valida vocabulário, não interpreta/executa); a alternância real (ligar/desligar e aplicar/remover os efeitos do while_active) fica a cargo da interface do VTT (bonfire-vtt). |
| `trigger` | 889 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=bind; op=gate; target=ativacao.gatilho | Vincula a um evento genérico ou a outra habilidade. |
| `unlock` | 0 | - | forma=block; op=grant_execution | Abrir/destrancar com chave, ferramenta ou teste: unlock{tools:ladrao, save{dex, cd=15}}. |
| `upcast` | 165 | classe-hab, item-magico, magia, talento, traco | forma=block; op=add_modifier | Escala por nível de espaço de magia (upcast:{dmg:+1d6/nivel}). |
| `uses` | 1225 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block; op=resource | uses{N, reset:<rest>} — pool de usos; também função dinâmica (ver functions.uses). |
| `utilize` | 2 | classe-hab, talento | forma=flag; op=grant_execution | Execução: ação Utilizar (2024) — usar um objeto. Família de search/study/help/dodge. Aprovado 2026_06_18. |
| `vuln` | 6 | classe-hab, opcao | forma=key_value; op=add_to_set; target=vulnerabilidades | - |
| `weapon_die` | 8 | classe-hab, opcao, talento, traco | forma=key_value; op=set_value; target=ataque.dado | Manipula o DADO de dano da arma. weapon_die:+1_step sobe a categoria (1d6→1d8); par de die_step / die_min. |
| `while` | 15 | classe-hab, item-mundano, traco | forma=block; op=gate | Bloco ativo CONDICIONAL: while:<cond>{<efeitos>} — efeitos valem ENQUANTO a condição se mantém (while:in_sunlight{...}). Estados de habilidades usam while:in:ability{...}{...}; não viram condições globais. |
| `while_active` | 478 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | forma=block; op=gate | Efeito que dura/alterna até acabar; corpo é bloco de efeitos. |
| `width` | 4 | traco | forma=key_value | Largura de uma área (linha/onda); par de radius/point. |
| `wield_item` | 3 | traco | forma=flag; op=set_value | Pode empunhar/usar itens nesta forma (formas que normalmente impediriam). |
| `willing` | 24 | classe-hab, opcao, talento, traco | forma=flag; op=pick | Só entram criaturas voluntárias; gera variável 'aliados_aceitos'. |
| `without` | 592 | bestiario, classe-hab, item-magico, opcao, talento, traco | forma=block; op=omit; target=execucao.omissoes | Omissão ligada a uma execução concreta: a execução acontece sem um custo, componente, rolagem, requisito operacional ou consequência que normalmente teria. Exemplos: cast{spell:x, without{slot}}, move:30ft(without{opportunity_attack}), dmg:ability_mod(without{roll}). Não representa proibição persistente, imunidade, supressão de bônus nem predicado negativo. |
### `recursos_universais`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `dados_de_vida` | 43 | item-magico, opcao, talento, traco | - | - |
| `inspiracao_heroica` | 10 | magia, talento, traco | - | - |
### `references`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `ability` | 578 | bestiario, classe, classe-hab, item-magico, opcao, talento, traco | - | - |
| `any_bestiary` | 1 | magia | - | - |
| `arma` | 15 | classe-hab, talento | - | - |
| `bestiary` | 62 | antecedente, bestiario, classe-hab, item-magico, magia, traco | - | - |
| `classe` | 384 | bestiario, classe-hab, opcao | - | - |
| `condition` | 23 | classe-hab, opcao, talento, traco | - | - |
| `identidade` | 0 | - | - | - |
| `local` | 0 | - | - | - |
| `opcao` | 46 | classe-hab, opcao, talento | - | - |
| `spell` | 2980 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | - |
### `scopes.atributo`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `dex_atk` | 6 | bestiario, classe-hab, talento | - | ataque por Destreza |
| `str_atk` | 8 | bestiario, classe-hab | - | ataque por Força |
### `scopes.defensivo`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `armor` | 28 | classe-hab, item-magico, opcao, talento, traco | - | bônus plano de CA que EMPILHA com a armadura equipada (armor.ca:+N — Estilo de Luta Defesa / infusões de armadura); distinto de ca= (base sem armadura). |
### `scopes.direcao_ataque`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `by` | 26 | classe-hab, item-magico, opcao, talento, traco | - | POR (quem faz o ataque): without{adv:attack{by:self}} = seus próprios ataques não têm Vantagem; dadv:attack{by:enemies} = ataques dos inimigos têm Desvantagem. |
| `vs` | 106 | antecedente, classe-hab, item-magico, magia, opcao, talento, traco | - | CONTRA (o alvo/vítima do ataque): em adv/dadv desambigua a direção. without{adv:attack{vs:self}} = nenhum ataque feito CONTRA você tem Vantagem. Sem vs:/by:, um target:self fica ambíguo (atacante vs vítima). |
### `scopes.distancia`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `melee` | 61 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | corpo a corpo |
| `ranged` | 64 | bestiario, classe-hab, item-magico, item-mundano, opcao, talento, traco | - | à distância |
### `scopes.empunhadura`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `free_hand` | 5 | classe-hab, opcao, talento, traco | - | ao menos uma mão livre (requires) |
| `off_hand` | 3 | opcao, talento | - | mão secundária |
| `one_handed` | 1 | opcao | - | uma mão |
| `two_handed` | 1 | opcao | - | duas mãos |
### `scopes.qualificadores_de_arma`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `heavy_weapon` | 3 | talento | - | arma pesada |
| `light_weapon` | 1 | opcao | - | arma leve |
### `scopes.rolagem_magica`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `magic` | 105 | bestiario, classe-hab, item-magico, magia, opcao, talento, traco | - | usa mod. de conjuração + PB |
### `scopes.situacional`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `grapple` | 5 | classe-hab, item-magico, talento, traco | - | manobra Agarrar: grapple.contest (ver contest{}) |
| `manobra` | 9 | classe-hab | - | perfil de Manobra de Combate (resource{dado_de_combate}): manobra.cd / manobra.<efeito> |
| `mount` | 5 | classe-hab, talento | - | montaria (Combatente Montado): mount.<efeito> |
### `scopes.tipo_fisico`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `natural` | 15 | classe-hab, item-magico, talento, traco | - | arma natural |
| `unarmed` | 41 | classe-hab, item-magico, opcao, talento, traco | - | desarmado |
| `unarmed_strike` | 39 | classe-hab, item-magico, opcao, talento, traco | - | golpe do Ataque Desarmado (perfil 2024) |
| `weapon` | 466 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | com arma |
### `selectors`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `active` | 38 | classe-hab, opcao, talento | - | o que estiver ativo no momento |
| `all` | 59 | bestiario, classe-hab, item-magico, talento, traco | - | todos no escopo |
| `allies` | 112 | classe-hab, item-magico, opcao, talento, traco | - | aliados |
| `away_from` | 3 | classe-hab | - | destino na direção oposta à fonte indicada; usado por movimento forçado sem criar uma condição específica |
| `bound` | 63 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | criatura vinculada |
| `chosen_enemies` | 15 | classe-hab, item-magico | - | inimigos escolhidos |
| `collision` | 1 | classe-hab | - | alvo de colisão (investida) |
| `companion` | 16 | classe-hab, traco | - | criatura_companheira controlada pelo personagem (Defensor de Aço, Familiar Primal, espíritos/mortos_vivos comandados — entradas do Bestiário) |
| `creature` | 163 | antecedente, classe-hab, item-magico, item-mundano, magia, opcao, talento, traco | - | uma criatura genérica |
| `enemies` | 123 | classe-hab, magia, opcao, talento, traco | - | inimigos |
| `guard` | 4 | classe-hab | - | criatura protegida (guardião) |
| `last_damage_type` | 14 | classe-hab, opcao, talento, traco | - | o último tipo de dano sofrido (muda em runtime) |
| `magic_object` | 2 | classe-hab | - | objeto mágico |
| `self` | 284 | bestiario, classe-hab, item-magico, opcao, talento, traco | - | o próprio personagem |
| `source` | 109 | classe-hab, essencia, item-magico, opcao, talento, traco | - | a fonte do dano/efeito recebido |
| `wielded` | 25 | classe-hab, talento, traco | - | arma/objeto empunhado |
### `tags_de_classe`

| Nome | Usos | Modelos | Contrato | Documentacao |
|---|---:|---|---|---|
| `asi_choices` | 13 | classe | op=set_value | Níveis com Incremento de Atributo/Talento. ÚNICA fonte de ASI — não existe choice:asi por habilidade; a feature é detectada por nome (_eh_feature_asi). |
| `background_grants` | 30 | antecedente | op=set_value | Metadado de criacao de personagem para antecedentes: ASI, pericias, idioma fixo, escolhas idioma/ferramenta, dinheiro inicial e alternativa de ouro do equipamento. |
| `hit_dice` | 13 | classe | op=set_value; target=classe.dado_vida | PV deriva do dado (motor, não tag). |
| `multiclass_prof` | 11 | classe | op=grant_proficiency; target=multiclasse.proficiencias | - |
| `multiclass_req` | 13 | classe | op=gate | - |
| `saves_prof` | 13 | classe | op=grant_proficiency; target=saves | - |
| `skills_lvl1` | 13 | classe | op=pick | - |
| `subclass_choices` | 14 | classe, classe-hab | op=set_value | Níveis DA classe com característica de subclasse; o 1º é onde se escolhe a subclasse. |

## Auditoria automatica

- Nenhum nome ativo usa hifen.
- Nenhum termo proibido permanece nas formulas.
- O CSV espelho esta em `C:/Users/helio/Desktop/Projetos Bonfas/BonfireSite-main/docs/agentes/listagem_tags_cadastradas_20260726.csv`.
