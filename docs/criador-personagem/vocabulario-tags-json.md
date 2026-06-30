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

### Regra: primitiva do vocabulário **vs** definido no JSON
A linha que separa "o backend conhece" de "está no JSON":

- **Primitiva do vocabulário** = um **verbo genérico** que o backend implementa
  **uma vez** e serve pra qualquer classe: `resist`, `aura`, `mark`, `roll`,
  `match`, `modify`, `action`, `pick`, `cast`, `if`, `save`… É um conjunto
  **pequeno e fixo**. Adicionar verbo novo = **consultar o PO** (vira hardcode).
- **Definido no JSON** = qualquer coisa **específica** de uma classe/habilidade:
  a tabela "magia-selvagem", a lista "runa", o "aspecto-selvagem", o poder
  "desperta" de cada runa. Vai num `define{}` e é **referenciado**.

> **Teste:** *"isso precisa de um verbo genérico novo no backend, ou dá pra
> compor com verbos que já existem + um `define`?"* Se dá pra compor, **não é
> vocabulário**. Ex.: "poder raivar de armadura pesada" não é um verbo novo —
> é `modify` removendo a restrição da Fúria. "Invocar a runa desperta" não é
> verbo novo — é uma `action:` que aponta para um efeito `define`-ido.

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
| `action=<tipo>` | tipo de ação p/ ativar **esta** habilidade: `action`·`bonus-action`·`reaction`·`free` |

### Custo de ação **≠** execução

Os **tipos de ação** são só quatro: `free`, `bonus-action`, `action`, `reaction`.
**Dash, Disengage, Atacar, Teleportar… NÃO são tipos de ação** — são **execuções**
(você *gasta* uma ação para fazê-las, assim como gasta a ação para Atacar).

- Ativação da própria habilidade: `action=<tipo>`.
- Conceder/gastar uma ação para executar algo, dentro de um efeito:
  `action:<tipo>, instant{<execução(ões)>}` (ou `action:<tipo> -> <execução>`).
  - ✅ `while-active{ action:bonus-action, instant{dash} }` — "pode Dashar com ação bônus".
  - ✅ `action:bonus-action, instant{attack:melee}` · `action:reaction, instant{aoe{...}}`.
  - ❌ `action:dash(bonus)` · ❌ `action:attack{natural}(bonus)` (confunde custo com execução).

Execuções comuns em `instant{}`: `dash`, `disengage`, `teleport:<dist>`, `attack:<perfil>`
(`melee`/`natural`/`unarmed`/…), `marcar`/`apply:<...>`, ou um nome de execução custom
cujo detalhe vive na descrição.

---

## 4. Gatilhos (`trigger=`)

Vincula a ativação a um **evento** ou a **outra habilidade**:

- `trigger=ability{<nome>, classe:<slug>}` — vincula a OUTRA habilidade (ex.: `trigger=ability{furia, classe:barbaro}`). Cobre tanto "enquanto X ativa" (com `while-active`) quanto "no momento que X ativa" (com `instant`). **Tudo que é específico de uma classe** (entrar em fúria, frenesi, dano dos espíritos…) vira referência a `ability{}`, NÃO um evento.
- `trigger=<evento>` — evento **genérico do jogo** (vale pra qualquer personagem).

A escolha de *sempre ativar / perguntar / perguntar quando muda o resultado*
(estilo *chain* de Yu-Gi-Oh) é **implícita** a todo trigger — não há tag.

**Eventos canônicos (só os genéricos):** `first-attack` · `hit-melee` ·
`crit-melee` · `hit-by-melee` · `drop-to-0` · `reduce-to-0` · `take-damage` ·
`fail-save` · `initiative` · `turn-start` · `turn-end` ·
`short-rest` · `long-rest` · `end` (fim da **duração ativa da própria habilidade** —
ex.: Frenesi, ao acabar, dá exaustão: `on:end -> exhaustion:+1`).

> `enter-rage`, `spirit-damage`, `frenesi` **não** são eventos — são específicos
> demais. Use `trigger=ability{furia|frenesi|...}` (o `instant`/`while-active`
> define se é "ao ativar" ou "enquanto ativo").

### Regra de ouro: nada de nome de classe "solto"

Uma tag **nunca** pode carregar o nome de uma habilidade/recurso específico de uma
classe como se fosse vocabulário genérico (`furia`, `frenesi`, `runa`…). Se a tag
**usa outra habilidade** — seu estado, seu valor, sua duração — ela **referencia**
com `ability{<nome>, classe:<slug>}` (e `.campo` para um valor exportado):

| ❌ Errado (nome solto) | ✅ Certo (referência) |
|---|---|
| `dmg:furia(fogo)` | `dmg:ability{furia, classe:barbaro}.dmg-bonus(fogo)` |
| `duration:furia` | `duration:ability{furia, classe:barbaro}` |
| `1/furia` | `1/ability{furia, classe:barbaro}` |
| `match(runa.ativa)` | `match(ability{runas-elementais, classe:barbaro}.runa.ativa)` |
| `on:furia-end` | `on:end` |

> **Exceção:** *variáveis internas* definidas com `define{}` (a tabela
> `magia-selvagem`, a lista `runa`, `aspecto-selvagem`…). Bare é OK **dentro da
> habilidade dona**; usada por outra habilidade, ainda vai por `ability{<dona>,
> classe:<slug>}.<variável>`. A própria Fúria expõe seu bônus por
> `define{dmg-bonus: roundup(classlvl/2)}`, referenciado como
> `ability{furia, classe:barbaro}.dmg-bonus`.

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

**`requires{...}`** é o **inverso** de `restriction`: uma **condição positiva** que
o efeito **exige** para funcionar (ex.: `requires:equiped{armadura-aprimorada}`,
`requires:runa-ativa`, `requires:weapon{vinculada}`). Sem ela, o efeito não se aplica.

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

## 6b. Tag da CLASSE (`TbClasse.tags_json`)

A própria **classe** carrega uma tag com a metadata que o motor usa (substitui
as colunas hoje vazias da `TbClasse`):

```
[ hit-dice:1d12,
  saves-prof{str, con},
  skills-lvl1{pick:N de [Atletismo, Intimidacao, ...]},
  subclass-choices{3, 6, 10, 14, 18},
  asi-choices{4, 8, 12, 16, 19},
  multiclass-req{str>=13},
  multiclass-prof{escudos, armas-simples, armas-marciais} ]
```

- `hit-dice:<dado>` — dado de vida; o PV deriva dele (§1.4 e §11).
- `saves-prof{<attr>…}` — testes de resistência proficientes da classe.
- `skills-lvl1{pick:N de […]}` — perícias que a classe concede no nível 1 (quantidade + lista).
- `subclass-choices{…}` — níveis **DA classe** com característica de subclasse; o **primeiro** (ex.: 3) é onde se **escolhe** a subclasse (cada classe escolhe a sua → multiclasse pode ter várias subclasses).
- `asi-choices{…}` — níveis com Incremento de Atributo/Talento.
- `multiclass-req{…}` / `multiclass-prof{…}` — requisito e proficiências ao multiclassar.

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
cast{ spell:detectar-magia, modifiers{ no-slot, always-prepared }, uses{1, reset:long-rest} }
```

Para magias inatas/concedidas que nao gastam espaco de magia, prefira declarar o
limite dentro do proprio `cast{}` com `uses{N, reset:long-rest}` ou
`uses{N, reset:short-rest}`. A ficha trata isso como recurso oculto da magia:
aparece na linha da magia como `1/day`, `3/day`, etc., mas nao entra na aba de
recursos consumiveis.

Formatos antigos ainda reconhecidos pelo motor/validador:

```
cast{ spell:detectar-magia, modifiers{ no-slot } }, resource-cost:1/long-rest
cast{ spell:detectar-magia, modifiers{ no-slot, 1/long-rest } }
```

---

## 9. Definir métodos/tabelas inline + override

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

O **corpo de cada resultado** (`N:{...}`) é um **bloco de efeito** montado com os verbos
genéricos de sempre (`dmg:`, `resist:`, `aoe{}`, `aura{}`, `action:`, `save{}`, `apply:`,
`move:`, `temp-hp:`, `trigger=`…). Dentro do bloco, `self.cd` = a CD da própria habilidade
e `furia` = o bônus de dano da Fúria. Efeito complexo demais para fórmula (teleporte, forma
fantasmal, crescer) vira `action:<nome>` cujo texto fica na descrição.

**Controle de tabela** (só fazem sentido dentro de `table{}`):
- `reroll` — rola de novo na mesma tabela.
- `apply-also` — acumula com o resultado atual (aplica os dois).

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
| `resource-cost:<recurso>` | consome uso (`resource-cost:furias`, `…:1/long-rest`, custo alt. `{1/long-rest \| furias}`) |
| `duration:<n>` | em **rodadas** (`duration:10`=1min) ou `until-next-turn` |
| `duration:ability{<nome>, classe:<slug>}` | dura **enquanto outra habilidade durar** (ex.: `duration:ability{furia, classe:barbaro}`) |
| `cd=<fórmula>` | classe de dificuldade (`cd=8+pb+con-mod`) |

> **Fúria não é "duração".** Uma habilidade não pode usar `duration:furia` — `furia`
> é uma **habilidade**, não um valor de tempo. Para "dura enquanto a Fúria durar" use
> a **referência correta**: `duration:ability{furia, classe:barbaro}` (mesma forma de
> todo `ability{}`). Idem para "fim da duração": use `on:end` (§4), não `on:furia-end`.

**Valores dinâmicos** — quando algo cresce com o uso:
`cd=10+5*uses{self, reset:rest}` (Fôlego Furioso: CD sobe 5 por uso, volta a 10
após descanso). `uses{self}` = nº de vezes que **esta** habilidade foi usada.

### Funções compostas (modelo Excel)
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
| **Área de efeito** | `aoe{ point:<dist>, radius:<dist>, save{...}, dmg:<...>, on-success:<half\|none> }` | explosão/área pontual (alvo um ponto, não emanação contínua); resolve teste + dano de uma vez |
| **Marca/contador** | `mark{ <nome>, on:<evento> -> <delta>, consume:<evento> -> <efeito> }` | acumula contadores em alvos e os consome num evento (ex.: Sede de Sangue → `temp-hp:+(con-mod * marks)`) |
| **Lista definível** | `define{ <nome>: list{ <chave>:{...}, … } }` + `pick:<nome>:N` | o corpo de cada `<chave>` é **bloco de efeito** (aspectos da fúria) **ou** **atributos tipados** (`pericias:[…]`, `elemento:[…]`); `pick` abre a escolha |
| **Arma definida/modificada** | `define:weapon{ <nome>: <dmg>+<mod>, <dano> }` · `<arma>.add-property{ <prop>… }` | perfil de ataque (armadura vira arma) ou propriedade nova (arremesso/retorno) |
| **Custo alternativo** | `resource-cost:{ <a> \| <b> }` | paga `a` **ou** `b` (ex.: `1/long-rest \| furias`) |

> **`aura{}` vs `aoe{}`:** `aura` é emanação **contínua** presa ao personagem (dura enquanto ativa);
> `aoe` é uma detonação **pontual** num lugar/instante (resolve teste + efeito e acaba).
> **Seletor dinâmico:** `resist:last-damage-type` resiste ao último tipo de dano sofrido (muda sozinho).

> **Criaturas voluntárias e contagem de aceitação.** `pick:aliados:N(range:<dist>, willing)`
> seleciona até `N` criaturas **voluntárias** (`willing` = só entram quem aceita). A
> **quantidade que aceitou** vira a variável de runtime **`aliados-aceitos`**, usável em
> fórmulas (igual a `marks` da Sede de Sangue) — ex.: `temp-hp:+(<valor> * aliados-aceitos)`.
> Esse padrão se repete em várias habilidades que afetam aliados voluntários.

> **Forma/transformação** não é primitiva nova — é `define{}` + `while-active{...}`.

## 14. Em aberto (a definir com o PO)

- Esquema do **parser** (string → JSON estruturado) e do **motor de derivação** (avaliador das funções/efeitos).

**Resolvidos** (2026-06-15, Bárbaro como molde):
- Pré-requisito de atributo → na **tag da classe** como `multiclass-req{str>=13}` (§6b).
- Cura por marca da **Sede de Sangue** → `consume:turn-end -> temp-hp:+(con-mod * marks)`.
- Poderes despertos das runas (Arauto Rúnico) → **sem verbo `invoke`**: o Despertar Rúnico usa
  `match(ability{runas-elementais, classe:barbaro}.runa.ativa){ chamas:{…}, … }` (switch que já existe, §10);
  a lista de runas (Runas Elementais) guarda só `elemento`.
- **Proficiência concedida** → `prof:<categoria>{<valor>}` (ex.: `prof:tool{ferreiro}`, `prof:armor{pesada}`).
  Evita o `prof:cat:val` de duplo dois-pontos (ambíguo com o separador de token).
- **Custo de ação ≠ execução** → `action:<tipo>, instant{<execução>}` (ver §3).
- **Nada de nome de classe solto** → referência sempre `ability{<nome>, classe:<slug>}.<campo>`;
  fim de duração própria via `on:end`; `furia` não é duração. Regra de ouro no §4.
- **`uses{self, reset:rest}`** e **funções compostas** (if/save/roll/match) → confirmados (saíram de *proposta*).
- Forma do corpo de `table{results{…}}` e `list{…}` → bloco de efeito genérico (§9, §13).

**Resolvidos** (2026-06-17, Monge como 2º molde marcial):
- **Pool de recurso NÃO é tag.** Vetado `resource{}` para declarar pool — recurso de classe vive na
  `TbRecursoclasse`; se não existir, escrever na tabela. Tag só referencia (`resource{<slug>}`), gasta
  (`resource-cost:<slug>:<N>`, **com quantidade**) ou restaura (`resource-restore:<slug>=all`). Ex.: Ki =
  recurso `pontos-de-ki`; Dado de Artes Marciais = recurso `artes-marciais` (não `define{}`).
  O campo `tipo` classifica o papel no builder: `table-only` = dado informativo/derivado da tabela
  (ex.: slots por nivel), `consumable` = pool gasto/rastreado na ficha (ex.: `furias`),
  `choice` = quantidade de escolhas que nao se gasta (ex.: maestrias de arma, magias conhecidas).
- **`miss`** (evento bidirecional), **`cleanse`** (remove condição), **`move:wall`/`move:liquid`**,
  limitador **`1/turn`**, família **`hit-by-*`**, **`on-fail`** → aprovados.
- **Evasão sem verbo próprio:** `source{aoe}.save{dex}.on-success:=none, on-fail:=half`.
- **CD de classe (Ki):** a habilidade-fonte expõe via `define{cd: 8+pb+wis-mod}`; as demais referenciam
  `ability{ki, classe:monge}.cd` (regra de ouro: referência, não repetição).

**Resolvidos** (2026-06-17, Ladino):
- **Distância canônica = `ft`** (pés). Converter tags antigas em metros (5ft=1.5m, 30ft=9m, 60ft=18m…).
- Aprovados: `first-turn`, `hide`, `dmg-reduction:half`, `no-adv-against-self`, condições
  `adv`/`no-dadv`/`not-moved`/`ally(range:ft)`/`target{acted|!acted|surprised}`, escopo `next-attack`,
  combinadores `requires:{a and b | c}`, e `acuidade` (finesse) no catálogo B7.
- **Ataque Furtivo:** `1/turn`, `requires:{adv | ally(range:5ft) and no-dadv}`, dano =
  `resource{dados-de-furtividade}d(dado-de-furtividade)`. **Técnica de Furtividade:**
  `pick:<tecnica>(cost:N de dados-de-furtividade)`.

> **Fonte de conteúdo das classes:** HTMLs do World Anvil em `ref/Classes/` (consultar em caso de dúvida).

Rascunho de trabalho (espelho do banco): `ref/criador_barbaro_tags.md` (regenerado de `TbClassehabilidade`).

---

## 15. Tags de EFEITO de magia (`TbMagia.tags_json`)

A magia **já tem campos estruturados** (`nivel`, `escola`, `casting_time`, `ritual`,
`duracao`, `concentracao`, `alcance`, `componentes`, `classes`, `subclasses`) — a tag
**não os repete**. A `tags_json` carrega só o **efeito mecânico** + escala por slot.
Reusa os verbos das habilidades; o que é específico de magia:

| Token | Significado |
|---|---|
| `dmg:<NdX>(<elemento>)` | dano; `(auto)` = sem rolagem (ex.: Mísseis Mágicos) |
| `save{<attr>}` + `on-success:half` | teste de resistência; metade no sucesso |
| `attack:magico` | magia com jogada de ataque (eixo de rolagem por conjuração) |
| `heal:<NdX>+spell-mod` | cura |
| `aoe{<forma>:<tam>}` | `cone`/`sphere`/`cube`/`line` + tamanho (origem; alcance fica no campo) |
| `targets:<N>` | nº de alvos/dardos |
| `buff:<stat>:+<N>` | bônus temporário (ex.: `buff:max-hp:+5`) |
| `apply:<condicao>` | condição (Caído, Cego…) |
| `upcast:{<delta>/nivel}` | escala por **nível de espaço de magia** acima do base (`em_niveis_superiores`) |

Ex.: **Bola de Fogo** = `[aoe{sphere:6m}, save{dex}, dmg:8d6(fogo), on-success:half, upcast:{dmg:+1d6/nivel}]`.
**Cura por slot**: `[heal:2d8+spell-mod, upcast:{heal:+2d8/nivel}]`.

> Elemento de **Força** = token `forca` (decisão do PO; não usar "energia").
> As ~211 magias de **efeito simples** (dano/cura/ataque) foram taggadas
> semi-automaticamente da descrição; as **complexas** (condições, invocação,
> múltiplos efeitos) ficam para tratamento manual.

---

## 16. Conjuração e progressões de classe (tags de habilidade)

| Token | Significado |
|---|---|
| `spellcasting{ ability:<attr>, slots:<full\|half\|third>, lista:<classe>, prepara:<conhecidas\|preparadas>, foco:<...> }` | declara a conjuração da classe. **`slots` é a fração de caster** para multiclasse: full (Bardo/Mago/…), half (Paladino/Caçador), third (Cavaleiro Arcano/Atirador). |
| `pick:pericia-expertise:{ <nivel>:<qtd> }` | **Especialização/Expertise é regra GLOBAL** — o motor dobra o PB em qualquer perícia marcada `pericia-expertise`. A tag só sinaliza a escolha; **não** se cria `expertise:dobra-pb`. |
| `spell-selection:<lista>{ efeito: magia-conhecida(...) }` | adiciona magia **conhecida** (permanente, não é efeito "enquanto ativo") escolhida de `<lista>` (ex.: `any`). `extra, fora-do-limite` = não conta no total de Magias Conhecidas. |

> **Slots compartilhados no multiclasse (importante):** espaços de magia NÃO são a
> soma dos slots de cada classe. Soma-se o **nível de conjurador** (full = nível
> inteiro, half = metade, third = um terço), e a tabela única de slots é lida com
> esse total. Por isso cada `spellcasting{}` declara `slots:full|half|third`.
