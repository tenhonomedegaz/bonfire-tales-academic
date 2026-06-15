# Vocabulário do `tags_json` (Criador de Personagem)

> **Doc canônico.** Sintaxe das tags mecânicas do criador de personagem do
> Bonfire Tales. Versão **0.2 — provisória**. Itens marcados *(proposta)* ainda
> precisam do aval do PO.

---

## 1. Propósito e princípios

`tags_json` descreve **o que uma habilidade/traço/talento faz mecanicamente**,
de forma que a ficha **derive o estado** do personagem e um futuro
**VTT/exportador** entenda a regra — **sem hardcode no backend**.

### Princípios
1. **O JSON é uma linguagem.** Quase uma segunda programação: o objetivo é que
   regras possam ser criadas/alteradas **sem mexer no backend**, e que no futuro
   jogadores escrevam suas próprias habilidades seguindo estas regras. Por isso:
   **quanto mais definido e genérico, melhor.**
2. **Mínimo hardcode.** Não existe método/efeito "mágico" sem definição. Se uma
   habilidade inventa uma mecânica nova (ex.: "magia-selvagem"), ela é
   **definida no próprio JSON** (§9), não referenciada como string que o backend
   teria que conhecer.
3. **A tag só descreve o que o banco ainda não sabe.** Não reclassifique o que
   já é estrutural: classe/subclasse (FK), quem acessa a opção (`TB_OpcaoJogo.Tipo`
   + `TB_AcessoOpcao`), origem racial (`Id_Raca`/`Id_Linhagem`/`Id_Essencia`).
4. **Derive de dados, não hardcode por classe.** Ex.: **PV** vem do dado de vida —
   nível 1 = dado cheio (1d10 → 10, 1d12 → 12); por nível seguinte = `dado/2 + 1`
   (1d10 → 6, 1d12 → 7). O motor calcula a partir do dado, sem tabela por classe.
5. **Fórmulas, não casos isolados (modelo "Excel").** Pense nas tags como
   **fórmulas de planilha** e no motor como o **Excel**: ele conhece só um conjunto
   pequeno de **funções genéricas** (`if(...)`, `save{...}`, `roll{...}`, `set` `:=`,
   `add` `:+`, `min`/`max`, `roundup`) e referências a outras "células"
   (`ability{...}`). Habilidades novas se **compõem** dessas funções. Se a tag ficar
   curta demais e empurrar a lógica pro backend, **prefira a tag mais explícita** —
   quanto menos código isolado por habilidade, melhor.

### Onde vivem
Campo `tags_json` (JSONField) em `TbTracoracial`, `TbClassehabilidade`,
`TbOpcaojogo`, `TbTalento` e demais catálogos.

---

## 2. Anatomia

Uma entrada é uma **expressão** `[...]` com **tokens** separados por vírgula:

| Forma | Uso | Exemplo |
|---|---|---|
| `flag` | liga algo sem valor | `always-active`, `no-concentration` |
| `chave:valor` | **efeito** | `resist:fogo`, `dmg:+1d6` |
| `chave=valor` | **vínculo / fórmula / identidade** | `trigger=...`, `ca=10+dex-mod+con-mod` |
| `bloco{...}` | agrupa tokens de um escopo | `while-active{...}`, `restriction{...}` |
| `escopo.efeito` | **escopo** do efeito (dot-path) | `str-atk.crit-range:+1` |
| `ref{...}` | **referência a entidade definida** | `ability{furia, classe:barbaro}` |
| `define{...}` | **define** método/tabela local | ver §9 |

Blocos **aninham**. `:` = efeito-com-valor; `=` = vínculo/fórmula/identidade.

### Escopo via dot-path
Em vez de `restriction`, restrinja **a quê** o efeito se aplica com `escopo.efeito`:

| Escopo | Significado |
|---|---|
| `weapon.` / `heavy-weapon.` / `light-weapon.` | ataque com arma (geral / pesada / leve) |
| `unarmed-strike.` | ataque desarmado |
| `str-atk.` / `dex-atk.` | ataque que usa o atributo |
| `melee.` / `ranged.` | corpo a corpo / à distância |

Ex.: `str-atk.crit-range:+1` (Instinto Brutal); `unarmed-strike.dmg={...}`;
`weapon.crit-dmg=+1d10` (Fúria Devastadora).

### Referência a entidade (`ref{...}`)
Aponta para algo **definido em outro lugar** — nunca uma string solta:

- `ability{<nome>, classe:<slug>}` — uma habilidade (ex.: `ability{furia, classe:barbaro}`).
- `spell:<slug>` — uma magia do catálogo.
- `opcao:<tipo>` — um tipo de `TB_OpcaoJogo`.
- `<nome-local>` — algo criado com `define{}` na mesma habilidade (§9).

---

## 3. Ativação

| Token | Significado |
|---|---|
| `always-active{...}` | passiva, sempre ligada (**sem** `action`) |
| `while-active{...}` | dura/alterna (ativado, com fim) |
| `instant{...}` | acontece e acaba |
| `action=<tipo>` | tipo de ação p/ ativar: `action`·`bonus-action`·`reaction`·`free` |

---

## 4. Gatilhos (`trigger=`)

Vincula a ativação a um **evento** ou a **outra habilidade**:

- `trigger=ability{<nome>, classe:<slug>}` — "enquanto/quando a habilidade X estiver ativa" (ex.: `trigger=ability{furia, classe:barbaro}` = enquanto enfurecido).
- `trigger=<evento>` — evento canônico abaixo.

A escolha de *sempre ativar / perguntar / perguntar quando muda o resultado*
(estilo *chain* de Yu-Gi-Oh) é **implícita** a todo trigger — não há tag.

**Eventos canônicos:** `enter-rage` · `first-attack` · `hit-melee` ·
`crit-melee` · `hit-by-melee` · `drop-to-0` · `reduce-to-0` · `take-damage` ·
`fail-save` · `initiative` · `turn-start` · `turn-end` ·
`short-rest` · `long-rest` · `spirit-damage`.

---

## 5. Restrições (2 níveis) — `restriction{}` / `equiped{}`

`restriction` significa **"NÃO pode"** (nunca "só pode"). O nível diz **o quê** é
restringido:

| Onde | Significa |
|---|---|
| **dentro** do efeito (`while-active{... restriction{...}}`) | o que o **efeito te impede** enquanto está ativo (ex.: em fúria não pode `spellcasting`, `concentration`) |
| **fora**, no topo (`restriction{...}`) | o que **impede ativar** o efeito (ex.: `unconscious`) |

`equiped{<item>}` é uma restrição por **equipamento equipado**
(`equiped{armor}`, `equiped{heavy-armor}`) — também pode aparecer nos dois níveis.

Vocabulário: `spellcasting`, `concentration`, `unconscious`, `incapacitated`,
`armor`, `heavy-armor`, …

---

## 6. Identidade / Filtro / Pré-requisito

Um identificador resolvido contra o banco (substitui tags-slug redundantes):

| Token | Resolve | Uso |
|---|---|---|
| `raca=<slug>` | `TbRaca.slug` | de **toda** a raça (`raca=humano`) |
| `linhagem=<slug>` | `TbLinhagem.slug` | exclusiva da linhagem (`linhagem=humano-erthari`) |
| `essencia=<slug>` / `essencia=null` | `TbEssencia.slug` | exclusiva de essência / **só linhagem** |
| `prereq=<ref>` | outra entidade/atributo | exige algo presente *(forma de atributo em revisão)* |

---

## 7. Escolhas (`pick:`)

Abre **N slots**; o catálogo vem do schema.

| Token | Escolhe de |
|---|---|
| `pick:opcao:<tipo>:N` | `TB_OpcaoJogo` (Tipo, acesso via `TB_AcessoOpcao`) |
| `pick:pericia:N` / `pick:idioma:N` / `pick:ferramenta:N` | listas |
| `pick:<local>:N` | algo definido com `define{}` (ex.: `pick:aspecto-selvagem:1`) |

Progressão acumulada por nível: `pick:pericia:{classlvl=5:1, classlvl=10:2}`.
`N` pode vir de recurso: `pick:opcao:maestria-de-arma:N(=recurso maestria-com-armas)`.

---

## 8. Efeitos

`<dano>`/`<condição>`/recursos em **PT canônico**; atributos em **inglês**
(`str/dex/con/int/wis/cha` + `-score/-mod/-save/-check`).

> **Operadores:** `:+` **soma/acumula** (empilha: `dmg:+1d6`) · `:=` **define/sobrescreve**
> (não empilha: `attacks:=2`, porque ataques extras não acumulam — exceto progressões
> próprias, ex.: Guerreiro `attacks:={classlvl=...}`, ou ganhos condicionais).

### Defesa / dano recebido
| Token | Efeito |
|---|---|
| `resist:<dano>` / `immune:` / `vuln:` | por **tipo** de dano |
| `resist:source{spell}` / `resist:source{magical-effect}` *(proposta)* | por **fonte**: todo dano de magia/efeito mágico, qualquer tipo |
| `cond-immune:<condição>` | imune à condição |
| `adv:<save>` / `dadv:<save>` | vant./desv. em teste de resistência |
| `ca=<fórmula>` | sobrescreve CA |
| `dmg-reduction:<valor>` | reduz dano recebido |

### Ofensiva (use escopo dot-path quando for parcial)
| Token | Efeito |
|---|---|
| `attack:+X` / `dmg:+<valor>` | bônus de ataque / dano (`dmg=+(roundup(classlvl/2))`) |
| `attacks:+1` | +1 ataque na Ação de Ataque (contador) |
| `<escopo>.crit-range:+N` / `<escopo>.crit-dmg=+<v>` | margem / dano de crítico |
| `<escopo>.dmg={classlvl=X:val, ...}` | dado de dano por nível |
| `apply:<condição>(save:..., duração)` | aplica condição ao alvo |

### Geral
| Token | Efeito |
|---|---|
| `adv:<check>` / `dadv:<check>` | vant./desv. (`adv:initiative`, `adv:str-check`) |
| `attr:<attr>-score+N` / `attr-max:<attr>-score=N` | altera valor / teto |
| `min:<check>=<valor>` | piso de resultado (`min:str-check=str-score`) |
| `speed:+X` · `fly:eq` · `nadar:eq` · `escalar:eq` · `size:` · `reach:+X` | movimento / corpo |
| `prof:<perícia\|armor:X\|tool:X\|weapon:X>` · `expertise:` · `save-prof:` | proficiências |
| `heal:<valor>` · `resource-restore:<recurso>=all` | cura / restaurar recurso |

### Conjuração concedida — `cast{...}`
```
cast{ spell:detectar-magia, modifiers{ range:+30, no-concentration, target:self } }
cast{ spell:comunhao-natureza, modifiers{ ritual, ability:wis-mod, no-slot } }
```

---

## 9. Definir métodos/tabelas inline + override *(proposta)*

Quando a habilidade cria uma mecânica nova (sem regra no backend), ela a
**define** no próprio JSON. Outras habilidades **referenciam** essa definição.

### Definição (tabela rolável)
```
define{
  magia-selvagem: table{ dice:1d12, results{
    1:  { ... efeito do 1 ... },
    2:  { ... },
    12: { reroll, apply-also }
  }}
}
... e usa: roll:magia-selvagem
```

### Referência a partir de outra habilidade
```
# Magia Instável referencia a tabela definida na Magia Selvagem (Nv 3):
roll: ability{magia-selvagem, classe:barbaro}.magia-selvagem
```

### Modificar outra habilidade (sem caso especial no backend)
O `roll{...}` é **genérico**:
`roll{ table:<ref>, dice:<NdX>, keep:{sum|highest|lowest|pick:K} }`. Logo, "rolar 2
dados e escolher 1" **não é mecânica nova** — é o mesmo `roll` com `dice:2d12,
keep:pick:1`. Caos Encarnado só aplica esse **override de propriedade** na rolagem
da Magia Selvagem:
```
modify: ability{magia-selvagem, classe:barbaro}.roll{ dice:=2d12, keep:=pick:1 }
```
O backend precisa só de **duas mecânicas genéricas**: avaliar `roll{}` e aplicar
override numa entidade referenciada — nada específico de Caos Encarnado.

---

## 10. Custo, duração e valores dinâmicos

| Token | Significado |
|---|---|
| `resource-cost:<recurso>` | consome uso (`resource-cost:furias`, `…:1/long-rest`) |
| `duration:<n>` | em **rodadas** (`duration:10`=1min); ou `duration:furia`, `until-next-turn` |
| `cd=<fórmula>` | classe de dificuldade (`cd=8+pb+con-mod`) |

**Valores dinâmicos** *(proposta)* — quando algo cresce com o uso:
`cd=10+5*uses{self, reset:rest}` (Fôlego Furioso: CD sobe 5 por uso, volta a 10
após descanso). `uses{self}` = nº de vezes que **esta** habilidade foi usada.

### Funções compostas (modelo Excel) *(proposta)*
O motor avalia funções genéricas, que **aninham**:
- `if( <cond> ): <then>` (opcional `else: <...>`) — ramo condicional.
- `save{ <attr>, cd=<fórmula> }` — rola um teste de resistência; vale como condição (sucesso/falha).
- `roll{ table:<ref>, dice:<NdX>, keep:<modo> }` — rolagem genérica (§9).
- `match(<seletor>){ <caso>:<valor>, …, default:<valor> }` — **switch**: escolhe
  **exatamente um** ramo (o primeiro que casa). Evita dupla aplicação em
  categorias que se sobrepõem (ex.: `heavy`/`light` também são `weapon`).
- operadores/funções: `:=` (set) · `:+` (add) · `min(...)` · `max(...)` · `roundup(...)`.

Ex.: **Fúria Devastadora** — dado de crítico por tipo de arma, sem somar duas vezes:
```
crit-dmg:+ match(weapon){ heavy:1d12, light:1d8, unarmed:1d12, default:1d10 }
```

Ex.: **Fôlego Furioso** — em fúria, ao cair a 0 PV, CON save de CD crescente → fica em 1 PV:
```
[ trigger=ability{furia, classe:barbaro}, trigger=drop-to-0,
  instant{ if( save{con, cd=10+5*uses{self, reset:rest}} ): hp:=1 } ]
```

---

## 11. Escala e derivação

- **Nível:** `classlvl` (da classe) ≠ `lvl` (total).
- **Funções:** `roundup()`, `rounddown()`, aritmética em fórmulas.
- **Recursos/modificadores:** `furias`, `pb`, `str-mod`, `con-mod`, …
- **Derivações do motor (não-tag):** PV (do dado de vida, §1.4), bônus de
  proficiência, slots de magia — calculados da progressão, sem hardcode por classe.

---

## 12. Exemplo comentado — Fúria

```
[ action=bonus-action,
  while-active{
    resist:concussao, resist:cortante, resist:perfurante,   # resistência física
    dmg=+(roundup(classlvl/2)),                              # dano de fúria (escala c/ nível de classe)
    dadv:int-check, adv:str-check, adv:str-save,             # desv. INT, vant. FOR
    restriction{ spellcasting, concentration }              # o efeito te IMPEDE de conjurar/concentrar
  },
  resource-cost:furias,           # gasta 1 uso de Fúria
  restriction{ unconscious },     # NÃO ativa se inconsciente
  equiped{ heavy-armor },         # NÃO ativa com armadura pesada
  duration:10 ]                   # 1 min = 10 rodadas
```

---

## 13. Primitivas: área, marcas, listas, armas, custo *(confirmadas)*

| Primitiva | Sintaxe | Uso |
|---|---|---|
| **Aura** | `aura{ radius:<dist>, target:<allies\|enemies\|all>, effects{...} }` | emanação centrada no personagem; aplica `effects` a quem está no raio enquanto ativa |
| **Marca/contador** | `mark{ <nome>, on:<evento> -> <delta>, consume:<evento> -> <efeito> }` | acumula contadores em alvos e os consome num evento (ex.: Sede de Sangue) |
| **Lista definível** | `define{ <nome>: list{ <chave>:{...}, … } }` + `pick:<nome>:N` | define opções no próprio JSON (aspectos da fúria, runas) e abre escolha |
| **Arma definida/modificada** | `define:weapon{ <nome>: <dmg>+<mod>, <dano> }` · `<arma>.add-property{ <prop>… }` | perfil de ataque (armadura vira arma) ou propriedade nova (arremesso/retorno) |
| **Custo alternativo** | `resource-cost:{ <a> \| <b> }` | paga `a` **ou** `b` (ex.: `1/long-rest \| 1 furia`) |

> **Forma/transformação** não é primitiva nova — é `define{}` + `while-active{...}`.

## 14. Em aberto (a definir com o PO)

- **Pré-requisito de atributo** (`for13` vs `prereq=str-score>=13`).
- **Condição positiva** ("só funciona com X equipado") — inverso de `restriction`/`equiped`; provável `requires{...}`.
- **Valores específicos** de algumas mecânicas (cura por marca da Sede de Sangue, poderes de cada runa do Despertar Rúnico) — preencher caso a caso.
- Esquema do **parser** (string → JSON estruturado) e do **motor de derivação**.

Rascunho de trabalho: `ref/criador_barbaro_tags.md` (Bárbaro, com notas do PO).
