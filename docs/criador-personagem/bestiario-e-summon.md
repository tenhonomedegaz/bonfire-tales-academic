# Bestiário & `summon` (Criador de Personagem)

> **Decisão (2026-06-17):** o verbo `summon` foi aprovado e **toda criatura invocável/companheiro
> vive no BESTIÁRIO** — nunca com o statblock solto na tag. A tag só **referencia**
> `summon:bestiary{<slug>}`; o bestiário guarda os atributos. Mesmo princípio do veto de
> recurso (pool vive na `TB_RecursoClasse`): o statblock vive no bestiário.

## 1. Por que isso importa
Muitas features de subclasse invocam/controlam criaturas: **Defensor de Aço** (Artífice),
**Familiar Primal** / **Reduto Elemental** (Druida), **Espírito das Profundezas** / **Tentáculo**
(Místico), **Comandar Mortos-Vivos** (Paladino), **Aliança Selvagem** / **Enxame** (Caçador),
elementais, feras de Forma Selvagem, etc. Todas são **a mesma coisa**: uma entidade com statblock.
Se cada tag descrevesse os stats, viraria hardcode duplicado. Logo: **uma fonte única — o bestiário.**

## 2. Estado atual
- Não existe model Django de bestiário. Hoje há só a tabela `bestiary` do **bot** (config em
  `BOT_POSTGRES_TABLES['bestiary']` / `SITE_POSTGRES_TABLES['bestiary']`), lida por query crua
  (mesmo padrão de `quests`/`items`/`organizations`).
- Ou seja: o conteúdo de monstros do bot está lá, mas **sem modelo estruturado** e **sem as
  criaturas-companheiras homebrew** (Defensor de Aço & cia. ainda não existem como entrada).

## 3. Proposta de modelo — `TbBestiario`
Tabela própria do site (managed), análoga às demais `TB_*`, com o statblock mínimo que o motor
da ficha/VTT precisa. Campos:

| Campo | Tipo | Nota |
|---|---|---|
| `nome`, `slug` | texto | slug = chave do `summon:bestiary{<slug>}` |
| `tipo` | catálogo `creature-type` (PT) | morto-vivo, besta, elemental, construto… |
| `tamanho` | catálogo `size` (PT) | miudo…descomunal |
| `nd` / `cr` | número | nível de desafio (filtro de Forma Selvagem usa `nd`) |
| `ca`, `pv` | número/fórmula | PV pode ser fórmula (ver §5) |
| `atributos` | json | {str,dex,con,int,wis,cha} |
| `deslocamento` | json | {walk,fly,swim,climb} em ft |
| `sentidos`, `idiomas`, `resistencias`, `imunidades`, `cond_imunidades` | json/listas | reusam os catálogos do `tag_library.json` |
| `ataques` | json (tags!) | cada ataque é um **bloco de efeito** no MESMO vocabulário (`attack:`, `dmg:`, `save{}`…) |
| `tracos` | json (tags) | traços passivos/ações também em tags |
| `tags_json` | json | igual às outras tabelas — efeitos estruturados |
| `companheiro_de` | FK opcional → `TbSubclasse`/`TbClasse` | marca companheiros de classe (Defensor de Aço → Artífice) |
| `descricao_markdown`, `imagem_url` | texto | ficha de exibição |

> **Reuso total do vocabulário:** ataques e traços do monstro são taggeados com os MESMOS verbos
> das habilidades de classe. O bestiário não inventa linguagem — é o mesmo `tags_json` aplicado a
> uma criatura em vez de um personagem.

## 4. Como `summon` referencia
- `summon:bestiary{<slug>}` — invoca 1.
- `summon:bestiary{<slug>}:N` — invoca N (N pode ser fórmula: `summon:bestiary{lobo}:roundup(classlvl/5)`).
- O motor instancia o statblock do bestiário e o coloca sob controle do invocador.

## 5. Companheiros que ESCALAM (o ponto delicado)
Companheiros como o **Defensor de Aço** crescem com o invocador (PV/ataque por PB/nível). Duas vias:
1. **Statblock com fórmulas** — o campo `pv`/`ataques` do bestiário aceita `pb`, `classlvl`,
   `spell-mod` etc. (as variáveis de fórmula do `tag_library.json`). Ex.: `pv: 5+5*classlvl`.
2. **`scaling` no summon** — `summon:bestiary{defensor-de-aco}(scaling:owner)` passa o contexto do
   dono; o bestiário declara o que lê do dono.

Recomendado: **via 1** (fórmula no statblock) por padrão; `scaling:owner` só quando o vínculo é
mais forte que números (ex.: usa a CD de magia do dono → `cd=ability{conjuracao, classe:X}.cd`).

## 6. Migração / próximos passos do bestiário
1. Criar o model `TbBestiario` + migration (managed).
2. **Importar** o bestiário do bot para `TbBestiario` (parser dos monstros existentes → statblock).
3. **Cadastrar os companheiros homebrew** que as subclasses citam (Defensor de Aço, Familiar Primal,
   espíritos, elementais de invocação) — taggeando ataques/traços no vocabulário.
4. Validar os `summon:bestiary{<slug>}` das tags de subclasse contra os slugs reais (hoje os
   agentes assumiram slugs; precisam casar com `TbBestiario.slug`).

> Enquanto o model não existe, as tags de subclasse já usam `summon:bestiary{<slug>}` com slugs
> provisórios — é só religar quando o bestiário estiver populado (mesma lógica dos slugs de magia).
