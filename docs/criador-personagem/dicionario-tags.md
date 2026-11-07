# Dicionário de keywords do `tags_json` — categorizado

> Referência canônica de **toda** keyword usada nas tags, agrupada por categoria.
> Retagging snake_case: veja `docs/agentes/regras_retagging_tags_json.md`.
> **Regra de idioma:** *keyword estrutural* (verbo/chave/seletor/função) = **inglês**;
> *valor de catálogo do jogo* (o que o jogador escolhe ou o sistema cataloga:
> perícia, dano, condição, criatura, tamanho, equipamento, propriedade de arma) =
> **português**; *nome próprio / variável `define` / slug* (específico do homebrew) =
> **português**.
>
> Antes de usar uma keyword nova, ache a categoria certa aqui. Keyword fora deste
> dicionário = **consultar o PO** (evita `dmg` vs `damage`, `light` ambíguo, etc.).

---

## A. KEYWORDS ESTRUTURAIS — inglês

### A1. Ativação
`always-active` · `while-active` · `instant` · `action=` (tipos: `free` · `bonus-action` · `action` · `reaction`) ·
`log-castable` *(metadado: pode ser executado pelo log da ficha; ex.: efeito persistente como `Encontrar Familiar`)*

### A2. Gatilhos / eventos *(genéricos)*
`trigger=` · `on:` · `first-attack` · `hit-melee` · `crit-melee` · `hit-by-melee` ·
`hit-thrown` · `drop-to-0` · `reduce-to-0` · `take-damage` · `fail-save` · `initiative` ·
`turn-start` · `turn-end` · `short-rest` · `long-rest` · `end` · `enter-aura`

### A3. Referência / definição
`ability{<nome>, classe:<slug>}` · `spell:<slug>` · `opcao:<tipo>` · `classe:<slug>` ·
`define{}` · `modify:` · `modifiers{}` ·
`any-bestiary{tipo:<tipo>, nd:<valor>}` *(seleção dinâmica do bestiário para `define{}` + `pick:`)*

### A4. Efeito — ofensa / dano
`dmg` *(verbo **e** valor; **nunca** `damage`)* · `crit-dmg` · `dmg-type` ·
`crit-range` · `attacks` · `attack:<tipo>` *(ver A4b)*

### A4b. Taxonomia de ataque *(inglês — eixos estruturais do sistema)*
Combina dois eixos ortogonais + o atributo da rolagem; **todos em inglês** (não são
valores de catálogo, e sim eixos do sistema):
- **Distância**: `melee` (corpo a corpo) · `ranged` (à distância)
- **Tipo físico**: `unarmed` (desarmado) · `weapon` (com arma) · `natural` (arma natural)
- **Rolagem mágica**: `magic` (usa mod. de conjuração + PB)
- **Atributo da rolagem**: `str-atk` · `dex-atk`

Usados em `attack:<tipo>` e como **escopo** (`melee.`, `ranged.`, `unarmed-strike.`,
`weapon.`, `str-atk.`, `dex-atk.`).

### A5. Efeito — defesa
`resist` · `dmg-reduction` · `cond-immune` *(valor = condição, PT)*

### A6. Efeito — cura / recurso
`heal` · `temp-hp` · `hp` · `resource` · `resource-cost` · `resource-restore` · `uses` · `reset`

### A7. Efeito — rolagem / teste
`adv` · `dadv` · `reroll` · `roll{}` · `save{}` · `cd=` *(CD do teste/efeito; **não** é duração)* ·
`same-cd` · `on-success` *(`half`/`none` no sucesso)* · `roll-add` · `keep` · `dice`

### A8. Efeito — movimento / corpo
`speed` · `move:` (`climb`/`swim`/`walk`) · `jump` · `size` *(valor = tamanho, PT)* ·
`reach` · `teleport` · `dash` · `disengage` · `move-through`

### A9. Efeito — estado / utilitário
`apply:` *(valor = condição, PT)* · `mark{}` · `grant` · `enhance` · `destroy` ·
`light:` *(iluminação — **≠** propriedade de arma `leve`)* · `speak:` *(valor = criatura, PT)* · `ca`

### A10. Área / alvo
`aura{}` · `aoe{}` · `radius` · `point` · `cone` · `sphere` · `cube` · `line` ·
`range` · `target` · `effects{}` · `in-aura` · `in-light`

### A11. Função / operador
`if()` · `match()` · `min()` · `max()` · `roundup()` · `rounddown()` · `:=` (set) ·
`:+` (add) · `unless` · `except` · `default` · `no-*` (`no-slot`, `no-material`,
`no-concentration`, `no-atk-roll`, `no-space`, `no-unconscious`→**`no-inconsciente`**)

### A12. Conjuração
`spellcasting{}` · `cast{}` · `spell-selection:` · `spell-slot` · `slots:` (`full`/`half`/`third`) ·
`focus:` · `ritual` · `upcast{}` · `known-caster` · `prepared-caster` · `known-spell` ·
`targets` · `buff`

#### Contrato canônico do motor de conjuração

As formas abaixo são as formas novas e mecânicas. Elas têm precedência sobre os
nomes legados desta seção; nenhum consumidor deve inferir comportamento pelo nome
da classe, habilidade ou recurso.

- `spellcasting{ability:<atributo>, slots{progression:<full|half|third|pact>, resource:<slug opcional>, cost:<formula opcional>}, list:<slug>, mode:<known|prepared>, spell_limit{resource:<slug>|formula:<expr>|fixed:<N>}, spell_level_limit{...}, cantrip_limit{...}, pool:<class_list|spellbook>, swap{event:level_up, max:<N|all>}, acquire{initial:<N>, level_up:<N>, transcribe{source:spell_scroll, cost_po:<expr>, time_hours:<expr>}}, focus:<tipo>}` declara o contrato inteiro da classe.
- `requires:spellcasting, modify:spellcasting{list}.add{spell:<slug>, ...}` amplia a lista efetiva de todas as classes conjuradoras do portador. Não concede, não prepara e não conta a magia como escolha feita.
- `modify:spellcasting{list}.remove{spell:<slug>, ...}` remove da lista efetiva na ordem em que o modificador aparece.
- `spell_scroll{spell:<slug>, level:<N>, save_dc:<N>, attack_bonus:<N>}` é o protocolo de pergaminho virtual. O catálogo da Oficina o deriva de `TbMagia`; não existe um item arbitrário por magia.
- `spell_component{spell:<slug>, kind:<consumable|focus>, cost_po:<N>}` é o protocolo de componente virtual. `consumable` é gasto; `focus` continua na mochila.
- `pick:opcao:escola_de_foco:{classlvl=1:1,classlvl=10:+1,classlvl=18:+1}` declara as escolhas progressivas de Escola de Foco. A transcrição consulta a opção escolhida para reduzir custo e tempo, sem testar o nome da subclasse.

Exemplo de conjurador por pontos:

```text
spellcasting{ability:int, slots{progression:pact, resource:pontos_de_misticismo, cost:spell_level}, list:mistico, mode:known, spell_level_limit{resource:ciclo_de_magia}}
```

### A13. Escolha / pré-requisito / restrição
`pick:` · `requires:` · `willing` · `restriction{}` · `restricts{}` · `equiped{}`

### A14. Escala / atributo *(variáveis de fórmula)*
`str`/`dex`/`con`/`int`/`wis`/`cha` + `_mod`/`_score`/`_save`/`_check` · `pb` · `classlvl` · `lvl`

### A15. Seletor
`self` · `all` · `allies` · `enemies` · `creature` · `active` · `guard` · `bound` ·
`wielded` · `chosen-enemies` · `source` · `last-damage-type` · `magic-object` · `collision`

### A16. Duração
`duration:` · `until-next-turn` · `until-turn-start` · `while:`

### A17. Tag da CLASSE
`hit-dice` · `saves-prof` · `skills-lvl1` · `subclass-choices` · `asi-choices` ·
`multiclass-req` · `multiclass-prof`

> Os níveis de ASI ficam **só** em `asi-choices`. **Não existe `choice:asi`** por
> habilidade — a feature de Aumento de Atributo é detectada pelo nome (`_eh_feature_asi`),
> sem tag própria.

---

## B. VALORES-CATÁLOGO — português

### B1. Tipo de dano
`fogo` · `frio` · `acido` · `veneno` · `necrotico` · `radiante` · `psiquico` ·
`trovejante` · `raio` *(= elétrico)* · `forca` · `concussao` · `cortante` · `perfurante`

### B2. Condição
`amedrontado` · `caido` · `cego` · `enfeiticado` · `inconsciente` · `incapacitado` ·
`exaustao` · `envenenado` · `agarrado` · `atordoado` · `paralisado` · `petrificado` ·
`restringido` · `surdo` · `doente` · `invisivel` · `possuido` *(dominação/controle direto)*

### B3. Tipo de criatura
`morto-vivo` · `besta` · *(humanoide, aberracao, …)*

### B4. Tamanho
`miudo` · `pequeno` · `medio` · `grande` · `enorme` · `descomunal`

### B5. Perícia *(as 18, PT)*
`atletismo` · `intimidacao` · `percepcao` · `sobrevivencia` · `furtividade` · `intuicao` ·
`investigacao` · `adestrar-animais` · `natureza` · `arcanismo` · … (catálogo de perícias)

### B6. Categoria de equipamento *(proficiência)*
`armadura-leve` · `armadura-media` · `armadura-pesada` · `armas-simples` · `armas-marciais` ·
`escudos` · `instrumento-musical` · `ferreiro` *(ferramenta)*

### B7. Propriedade de arma
`leve` · `pesada` · `arremesso` · `retorna` · `acuidade` *(= finesse)* · *(versatil, sutil, alcance, municao, recarga…)*

---

## C. NOMES PRÓPRIOS / VARIÁVEIS `define` / SLUGS — português

- **Habilidades** (`ability{...}`): `furia`, `frenesi`, `inspiracao-bardica`, `despertar-bestial`, `guardioes-ancestrais`, `runas-elementais`, …
- **Recursos**: `furias`, `inspiracao-bardica` (usos), `dado-de-inspiracao` (valor do dado), `dado-de-combate` (valor do dado), `quantidade-de-dados` (usos), `dado-de-cacador` (valor do dado), `pontos-de-segredo` (usos), `segredos` (escolhas), `dados-de-furtividade` (quantidade de dados do Ataque Furtivo), `dado-de-furtividade` (valor do dado), `maestria-com-armas`
- **Variáveis `define`**: `magia_selvagem`, `runa`, `aspecto_selvagem`, `adaptacao`, `ferida`, `marca_guardiao`, `dmg_bonus`, `sangue`, `forma_sagrada`, `couraca`, `agil`, `alfa`, `chamas`, `tempestade`, `erosao`, `nevasca`
- **Slugs de magia** (`spell:`): `detectar-magia`, `comunhao-com-a-natureza`, `augurio`, `clarividencia`, `elementalismo`
- **Slugs de classe** (`classe:`): `barbaro`, `bardo`, `cacador`, …

---

## D. Taxonomia de ATAQUE — **resolvida** (ver A4b)

Mantida em **inglês** (são eixos estruturais do sistema, não valores de catálogo):
`melee`/`ranged` (distância) × `unarmed`/`weapon`/`natural` (tipo físico) / `magic`
(rolagem mágica), com `str-atk`/`dex-atk` para o atributo da rolagem.
**Pendência de banco:** padronizar os `attack:magico` (vindos do tagueamento de magia)
para `attack:magic`.

---

## Atualização 2026-06-17 — molde do Monge (decisões do PO)
**Verbos novos aprovados:**
- **A2** `miss` *(evento bidirecional: você erra um ataque OU um ataque contra você erra)*;
  `hit-by-melee`/`hit-by-ranged`/`hit-by-attack` *(ser acertado — família simétrica de `hit-*`)*.
- **A7** `on-fail` *(contraparte de `on-success`)*. **Evasão** = `source{aoe}.save{dex}.on-success:=none, on-fail:=half` — **não** se cria verbo `evasion`.
- **A9** `cleanse:<condição>` *(remove condição; inverso de `apply`)*.
- **A8** `move:wall` *(sobe superfícies verticais)* · `move:liquid` *(anda sobre líquidos)*.
- **A11** limitador `1/turn` *(uma vez por turno; oficializa uso já existente no Bárbaro)*.

**Vetado:** verbo `resource{}` para **declarar pool**. Recurso de classe vive na **`TB_RecursoClasse`**;
se não existir lá, **escrever na tabela**. A tag só **referencia** (`resource{<slug>}`), **gasta**
(`resource-cost:<slug>:<N>` — quantidade aprovada) ou **restaura** (`resource-restore:<slug>=all`).

**Pendência de dado (Monge):** features de subclasse (Punho do Dragão, Punho Bêbado…) estão
com `id_subclasse` **nulo** na `TB_ClasseHabilidade` (penduradas na classe base) — religar.

### Adendo — molde do Ladino (decisões do PO)
**Padrão de distância = `ft` (pés).** Converter tags antigas em metros: `5ft=1.5m · 10ft=3m ·
15ft=4.5m · 20ft=6m · 30ft=9m · 60ft=18m · 90ft=27m`.

**Verbos/condições novos aprovados:**
- **A2** `first-turn` *(primeiro turno no combate)*.
- **A8** `hide` *(execução: Esconder-se)*.
- **A5** `dmg-reduction:half` *(metade, arredonda p/ baixo)* · `no-adv-against-self` *(ninguém tem Vantagem contra você; `unless:incapacitated`)*.
- **Condições** (`requires:`/`if()`): `adv` · `no-dadv` · `not-moved` · `ally(range:<ft>)` ·
  `target{acted}`/`target{!acted}` · `target{surprised}`; escopo `next-attack`. Combinadores `{a and b | c}`.
- **Técnica de Furtividade:** `pick:<tecnica>(cost:N de dados-de-furtividade)` *(troca quantidade de dados do Ataque Furtivo por efeito; o tamanho do dado vem de `dado-de-furtividade`)*.

---

### Adendo — sweep das 9 classes (verbos aprovados 2026-06-17, detalhe no `tag_library.json`)
- **A7** `check-bonus:<perícia>=<f>` · `check-attr:<perícia>:=<attr>` (troca o atributo) · `all-saves:+<f>` · `auto-save-success` · `roll-add`.
- **A8** `push:<ft>` · `pull:<ft>` (movimento forçado).
- **A9** `sense:` · `detect:` · `telepathy` · `share-senses` · `grant:extra-action` · `cleanse:magia`.
- **A12** `slots:pact(resource:<slug>)` · `spell-selection{always-prepared}` · `cast{spell:pick{lista, nivel<=N}}`.
- **Eventos** `fail-check` · `save-roll` · `magic.deal-dmg`. **Limitadores** `1/spell` · `1/attack` · `1/combat`.
- **no-*** `no-los` · `no-somatic` · `no-verbal` · `no-sleep` · `no-crit-mult`. **Reset** `level-up` · `2d4-long-rest`.
- **Catálogo** `raridade` (comum…lendário). **Var** `spell-mod` (atributo de conjuração; **não** usar `ability:` solto — colide com `ability{}`).
- **Referência** `ability{<nome>, <fonte>:<slug>}` aceita `classe`/`talento`/`raca`/`linhagem`/`essencia` (motor precisa resolver além de classe).
- **Itens** `sintonizacao` (teto 3; `attr-max:sintonizacao=N` eleva).

---

### Adendo — vocabulário das OPÇÕES DE JOGO (aprovado 2026-06-18, detalhe no `tag_library.json`)
- **Condição** `silenciado`. **Escopos de empunhadura** `off-hand`/`one-handed`/`two-handed`/`free-hand`.
- **Eventos** `after-attack-action`, `enemy-enters-reach`, `enemy-enters-aura`, `enemy-moves-within-aura`, família `enter-area`, `target-miss`, `enemy-end-turn`.
- **Primitivas** `no-opportunity-attack`, `contest{}` (teste contestado), `die-min`/`die:-1-step`, `read:`, `repeatable`, `teleport:swap`/`reposition`.
- **Extensões**: `ca:+<f>(target:..., against:..., duration:...)` *(bônus temporário; ≠ `ca=` que sobrescreve)*; `grant:reaction{<exec>}(target:ally)`; `attack:opportunity`; `repeat-save:now`; `cleanse:doenca`; `modify:spell.casting-time`; `cast{spell:school:<x>}` *(filtro por escola)*; `modify:spell{escolhido}`; `resource-cost:<rec>:N` *(custo em quantidade; em recurso `table-only` como `dados-de-furtividade`, é abatimento local da ativação, não tracker persistente)*; `sense:see-through-objects`/`sense-through`; `color-vision`; `no-reaction`/`no-trace`/`no-read-thoughts`/`no-instant-death`.
- **Variáveis** `spent` (gasto efetivo), `dado-de-combate`, `dado-de-cacador`, `dado-de-furtividade`, `ability-mod`. **Catálogo** `kit-de-venenos` (ferramenta).
- **Pendência de dado:** Virtudes = Paladino → recurso `conviccao` + habilidade `golpe-da-conviccao` faltam (sistema de Convicção do **rework**); `weapon{kensei}`/`weapon{pacto}` pedem `define{}` na feature da subclasse.

---

### Adendo — Essência Elemental, versão final (aprovado 2026-06-22, detalhe no `tag_library.json`)
- **A5 (defesa)** `absorb:<dano>` — em vez de sofrer o dano daquele tipo, **anula** e **cura PV igual** ao dano que sofreria. Usado nas **Investiduras** (nv17) na ramificação `if(already:immune{<dano>}): absorb:<dano> else: immune:<dano>` (quando o personagem JÁ é imune, a Imunidade vira absorção). Valor = `damage-type` (PT).
- **A5 (defesa)** `immune-effect:<efeito>(requires:source{...})` — imune a um **efeito de movimento forçado/posição** que **não** é condição catalogada (empurrar/derrubar). Ex.: Investidura da Pedra `immune-effect:push(requires:source{nonmagical})`. Distinto de `cond-immune:` (condição) e de `immune:` (tipo de dano).
- **Padrão "ganhar um talento"** = `grant:ability{<slug>, talento:<slug>}` (a fonte `talento:` faz o validador pular o #REF!; resolve contra `TbTalento`). **Não** usar `pick:opcao:talento` (`talento` não é `TB_OpcaoJogo.Tipo` → WARN) nem o `pick:pick:talento` legado (malformado).

---

## Duplicatas resolvidas
- `cd=` saiu de **A16 (Duração)** → **A7 (rolagem)**: é Classe de Dificuldade, não duração.
- `same-cd` saiu de **A11** → **A7** (anda junto de `cd=`).
- `on-success` saiu de **A12** → **A7** (resultado de teste, não é exclusivo de magia).
- `choice:asi` **removido** (redundante com `asi-choices`; ASI é detectado por nome).
- `choice:` genérico **removido** de A13 (só o `choice:asi` o usava; escolha = `pick:`).
- `dmg_bonus` **removido** de A4 (é variável `define`, fica só em C).
- taxonomia de ataque: **inglês** (A4b), `attack:magico` → `attack:magic` no banco.
- `damage` → **`dmg`** (verbo e valor são o mesmo token).
- `light` (arma) → **`leve`** (propriedade de arma, B7); `light:` (iluminação) fica em A9.
- `thrown`/`returns` → **`arremesso`/`retorna`** (B7).
- `eletrico` → **`raio`** (B1).
- `morto-vivo`/`besta`/`grande` voltaram a PT (B3/B4); condições e equipamento → PT.
