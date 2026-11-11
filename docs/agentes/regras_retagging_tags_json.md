# Regras de retagging do DSL `tags_json`

Este guia e para o agente que vai retaggear o banco. Nao e uma lista de
substituicoes cegas: e uma especificacao de linguagem. Pense nas tags como
formulas de Excel ou como uma pequena linguagem de programacao de regras de RPG.

## Objetivo

- Nenhum identificador mecanico novo deve usar hifen.
- Identificadores usam `snake_case`: `while_active`, `resource_cost`,
  `dex_mod`, `dmg_bonus`, `armadura_pesada`.
- O caractere `-` fica reservado para operador matematico/unario em formulas,
3
- O retagging deve mudar tags, biblioteca e docs juntos, mas nao precisa mudar
  os slugs reais das tabelas do banco na mesma etapa.

## Alfabeto de identificadores

Forma canonica:

```text
[a-z][a-z0-9_]*
```

Valido:

```text
while_active
always_active
resource_cost
bonus_action
str_atk
unarmed_strike
dmg_bonus
spell_slot
long_rest
armadura_pesada
```

Invalido em tags novas:

```text
while-active
always-active
resource-cost
bonus-action
str-atk
unarmed-strike
dmg-bonus
spell-slot
long-rest
armadura-pesada
```

## Referencias ao banco

O banco ainda pode ter slugs com hifen. Dentro das tags, use o identificador
seguro em `snake_case` e deixe o resolvedor normalizar para o slug do banco.

Exemplos:

```text
spell:detectar_magia          -> resolve TbMagia.slug detectar-magia
classe:coracao_sagrado        -> resolve slug coracao-sagrado
bestiary{lobo_atroz}          -> resolve slug lobo-atroz
ability{furia, classe:barbaro}
```

Regra: nunca use uma string solta quando a linguagem tem referencia estruturada.

```text
Errado:  trigger=furia
Certo:   trigger=ability{furia, classe:barbaro}
```

## Escopo e ordem

A ordem e as chaves importam. O parser deve ler uma tag como AST, nao como texto
livre.

1. Uma `restriction{...}` no topo da habilidade bloqueia a habilidade inteira.
2. Uma `restriction{...}` dentro de `while_active{...}`, `always_active{...}`,
   `instant{...}`, `aura{...}` ou outro bloco bloqueia somente aquele bloco.
3. `restricts{...}` nao bloqueia a ativacao. Ele cria uma proibicao imposta
   pelo efeito ativo.
4. `requires{...}` e uma pre-condicao positiva: se nao cumprir, o escopo nao
   funciona.
5. Nao confie em "a linha de baixo pertence a de cima". Se a regra pertence a
   um efeito especifico, coloque dentro das chaves desse efeito.

Exemplo correto, estilo Furia:

```text
action=bonus_action
resource_cost:furias
restriction{inconsciente, equiped{armadura_pesada}}
while_active{
  resist:concussao,
  resist:cortante,
  resist:perfurante,
  str_atk.dmg:+(dmg_bonus),
  restricts{spellcasting, concentration}
}
define{dmg_bonus:roundup(classlvl/2)}
duration:10
```

Exemplo correto de restricao parcial:

```text
always_active{restriction{equiped{armor}}, ca=10+dex_mod+con_mod}
always_active{unarmed_strike.dmg={classlvl=1:1d6, classlvl=5:1d8}+str_mod}
```

Errado, porque a restricao vira ambigua ou global demais:

```text
always_active{ca=10+dex_mod+con_mod}
restriction{equiped{armor}}
always_active{unarmed_strike.dmg=1d6+str_mod}
```

## Primitivas e composicao

Nao crie primitiva especifica para um caso se um primitivo generico resolve.

Errado:

```text
furtividade_desvantagem
ca_base
forca_minima
nao_conjura_em_furia
```

Certo:

```text
dadv:furtividade
ca=12+dex_mod
requires{str_score>=15}
while_active{restricts{spellcasting, concentration}}
```

Antes de criar verbo novo, pergunte:

- Isto serve para qualquer regra de RPG, ou so para uma habilidade?
- Da para compor com `requires`, `restriction`, `restricts`, `if`, `match`,
  `save`, `roll`, `aura`, `aoe`, `apply`, `modify`, `define`?
- O dado ja existe como coluna no banco? Se existe, nao repita como tag.

## Operadores fazem parte da semantica

O operador nao e decoracao. O mesmo target pode receber atribuicao ou
modificador:

```text
ca=10+dex_mod       # set_value: define uma formula-base
ca:+2               # add_modifier: soma 2 ao valor resultante
speed:-10ft         # add_modifier negativo
attacks:=2          # substituicao explicita
```

Nunca normalize `=`, `:=` e `:+` como se fossem equivalentes. Um consumidor
deve despachar pelo trio `op`, `target` e operando tipado emitido pelo evaluator.
Ele nao deve procurar o nome literal da primitiva por regex.

Operandos compostos tambem sao dados estruturados:

```text
prof:armor{light}
sense:darkvision(range:120ft, if_present)
check_bonus:religiao=max(wis_mod,1)
```

O AST representa esses exemplos como nome, argumentos posicionais, kwargs,
flags e binding. Nao crie um regex por habilidade para extrai-los novamente.

## Escopos declarativos e de runtime

Blocos declarativos ou ainda nao executados nao concedem seus efeitos internos:

```text
define{opcoes:list{a:{resist:fogo}, b:{immune:frio}}}
match(tipo){a:{speed:+10}, b:{speed:+20}}
trigger=hit{instant{dmg:+1d6}}
```

`define`, `list`, `table`, `pick`, `match`, `if/else`, `trigger`, `instant`,
`while_active`, `cast`, `save`, `aura` e `aoe` preservam os efeitos para o
runtime ou ate uma escolha resolver o ramo. O character builder nao pode
materializar todos os filhos desses blocos como passivos.

`always_active` e a excecao intencional: seus filhos sao materializados quando
os gates do proprio escopo forem satisfeitos.

## Condicoes relacionais

Uma condicao e um valor do catalogo; quem a causa ou sofre e argumento:

```text
condition{amedrontado, source:self}
condition{agarrado, source:self, target:creature}
condition{incapacitado, target:self}
```

Sao invalidos identificadores como `amedrontado_by_self`,
`agarrado_por_self` e `incapacitado_self`. Se surgir uma nova relacao, amplie
os argumentos de `condition`; nao crie uma condicao nova para cada combinacao.

## Condicionais

Use condicionais genericos, nunca verbos de caso unico.

```text
if(<cond>): <efeito> [else: <efeito>]
match(<seletor>){caso_a:<efeito>, caso_b:<efeito>, default:<efeito>}
requires{<cond>}
restriction{<cond>}
```

Exemplo:

```text
instant{if(save{dex, cd=8+pb+dex_mod}): dmg:half}
```

Se a regra exigir `elif`, prefira `match` quando estiver escolhendo entre casos
nomeados. Use `if/else` para condicoes booleanas.

## Negacao, omissao e proibicao

Essas operacoes nao sao sinonimos. A escolha do verbo determina quem produz a
regra e por quanto tempo ela existe.

`without{...}` e somente um modificador de uma execucao concreta. A execucao
acontece, mas omite algo que normalmente faria parte dela:

```text
cast{spell:escuridao, without{slot}, without{material}}
move:30ft(without{opportunity_attack})
dmg:ability_mod(without{roll})
```

`restricts{...}` e uma proibicao imposta por um efeito ativo:

```text
while_active{restricts{spellcasting, concentration}}
aura{target:enemies, effects{restricts{heal, teleport}}}
```

`suppress{...}` desliga um efeito, modificador ou regra, sem proibir a acao:

```text
suppress{adv:attack{vs:self}}
suppress{condition{inconsciente}, trigger:hp=0}
suppress{penalty:passive_perception}
```

`immune_effect:` torna o alvo imune a um efeito externo:

```text
immune_effect:surprise
immune_effect:forced_movement(except:teleport)
immune_effect:sleep(source:magia)
```

`not{...}` nega somente um predicado booleano:

```text
requires{not{condition{incapacitado, target:self}}}
restriction{not{equipped{mascara_da_piedade}}}
if(not{space:available}): reroll
```

Nunca use `without{heal}` para dizer que uma criatura nao pode recuperar PV,
nem `without{adv:attack}` para remover uma vantagem ativa. O primeiro caso e
`restricts{heal}`; o segundo e `suppress{adv:attack}`.

Necessidades fisiologicas usam a propriedade generica `need`:

```text
need:air=false
need:food=false
need:water=false
need:sleep=false
```

## Sentidos

`darkvision` e `devilsight` sempre sao sentidos independentes. Uma regra que
concede Visao no Escuro comum declara apenas `darkvision`. Se a mesma regra
tambem permite enxergar atraves de escuridao magica, ela declara ambos:

```text
sense:darkvision(range:120ft)
sense:devilsight(range:120ft)
```

E invalido escrever `sense:darkvision(range:120ft, magical)` ou tratar
`devilsight` como melhoria embutida em `darkvision`.

## Ordem canonica recomendada

Dentro de cada registro, organize as tags nesta ordem:

1. `define{...}` que exporta variaveis/tabelas/armas locais.
2. Gates globais: `requires{...}` e `restriction{...}` da habilidade inteira.
3. Ativacao: `trigger=...`, `action=...`, `resource_cost:...`, `uses{...}`.
4. Blocos de efeito: `instant{...}`, `while_active{...}`, `always_active{...}`.
5. Duracao, reset, limite e notas mecanicas: `duration:...`, `reset:...`,
   `1/turn`, `limit:...`.

Se uma `restriction` ou `requires` so vale para um item do passo 4, ela deve
ficar dentro do bloco desse item, mesmo que isso quebre a ordem visual acima.

## Conversoes comuns

```text
while-active       -> while_active
always-active      -> always_active
resource-cost      -> resource_cost
resource-restore   -> resource_restore
bonus-action       -> bonus_action
long-rest          -> long_rest
short-rest         -> short_rest
spell-slot         -> spell_slot
no-slot            -> cast{..., without{slot}}
no-concentration   -> cast{..., without{concentration}}
str-atk            -> str_atk
dex-check          -> dex_check
unarmed-strike     -> unarmed_strike
dmg-bonus          -> dmg_bonus
difficult-terrain  -> difficult_terrain
armadura-pesada    -> armadura_pesada
```

## Validacao

Durante o retagging, rode o validador em modo estrito:

```powershell
$env:POSTGRES_URL=''
$env:DB_ENGINE=''
.\.venv\Scripts\python.exe manage.py validate_tags --no-db --strict-names
```

Com banco/referencias disponiveis:

```powershell
.\.venv\Scripts\python.exe manage.py validate_tags --strict-names
```

O modo `--strict-names` deve retornar zero `nome-com-hifen` antes do retagging
ser considerado pronto.

## Checklist de entrega

- Nenhum identificador mecanico com hifen.
- `restriction` global apenas quando a habilidade inteira e bloqueada.
- `restriction` local dentro do bloco afetado quando a restricao e parcial.
- `restricts` usado para proibicoes impostas por efeitos ativos.
- Nenhum dado estrutural do banco repetido como tag.
- Nenhuma primitiva especifica demais criada sem necessidade.
- `=`, `:=`, `:+` e `:-` preservam semanticas distintas.
- Blocos declarativos/runtime nao vazam efeitos estaticos para a ficha.
- Condicoes relacionais usam `source`/`target`, nunca sufixos no identificador.
- `tag_library.json`, docs e tags do banco usam a mesma nomenclatura.
- Relatorio com contagem de linhas alteradas por tabela e lista de pendencias.
