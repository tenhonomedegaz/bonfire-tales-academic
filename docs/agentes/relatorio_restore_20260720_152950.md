# Restore de conteúdo prod (dev-vence) — 2026-07-20 15:29:50 — PACOTE FINAL DE DEPLOY (escudos +2/+3 corrigidos)

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260720_152950.json` (5012 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260720_152950.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF puro):** `a60919898da6a323c9ae2321adc9c322c55843cb4436898c47a98e14994566ed`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise / rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
- **Substitui (baseline):** `restore_consolidado_20260720_060551.json` (pacote final, 5012 registros — esta versão o supersede, corrigindo os escudos +2/+3).

> **POLÍTICA NOVA DE ENTREGA (PO):** o `.json` e o `.report.json` ficam **SÓ NO DISCO** em
> `ref/backups/` (pasta **gitignored**) — **não são commitados** e **não** entram com `git add -f`.
> O PO sobe o `.json` pelo console de admin. **Só este relatório `.md` é versionado.**

## Painel de Merge (como o `sincronizar_conteudo` classifica)

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento, TbItemMagico,
  TbCosmetico`. Casa por `slug`, atualiza os campos, mantém o ID que a memória referencia.
  (`TbConquista` está na lista mas tem 0 linhas no dev → ausente do fixture.)
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade, TbRecursoclasse,
  TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra, TbRecompensaMestre,
  TbItemMundano, TbBestiario`. (`TbArmadilha` está na lista mas tem 0 linhas → ausente → tabela
  preservada na prod.)
- **FORA do arquivo (de propósito):** `TbRegiao, TbTerritorio, TbMapMarker, TbMapDesenho`
  (mundo/mapa — prod vence, preservado por ausência), `TbOrganizacao` e `TbMapLayer` (fora de
  qualquer lista de sync) e **toda a memória** (usuários, personagens, transações, bot). O
  aplicador **pula e preserva** qualquer modelo ausente no fixture.

## O que mudou nesta versão

**CORREÇÃO FINAL (vs baseline `20260720_060551`) — escudos mágicos +2/+3:** pela semântica do motor
(`home/item_mecanica.py` `_CA_ADD` + `home/character_engine.py` `_armadura_equipada`/`apply_tags`),
`ca:+N` de escudo é a **CA TOTAL** que o escudo concede em jogo (um escudo comum já dá +2). Então:
**`TbItemMagico` pk20 `+2 Escudo (*)` `ca:+2` → `ca:+4`** (base 2 + 2 mágico) e **pk32 `+3 Escudo (*)`
`ca:+3` → `ca:+5`** (base 2 + 3 mágico). O **pk7 `+1 Escudo (*)`** já estava correto (`ca:+3`) e **não
foi tocado**. Diff vs 060551: **APENAS `TbItemMagico`, 2 registros de valor (pk20/pk32), 0 mudança de
linha** — as outras 20 tabelas de conteúdo batem `sha256_registros` exatamente com 060551 (só muda o
`sha256_arquivo` e o `sha256_registros` de `TbItemMagico`).

### Cumulativo vs `20260719_200533`

Log de conteúdo: **1866 entradas** em `conteudo_final/log_conteudo.jsonl`. As ações:

| Ação | Campo | Nº | Tabela |
|---|---|---:|---|
| `remove_metadado` | `tags_json` | 953 | TbItemMagico |
| `reformat_descricao` | `descricao_markdown` | 470 | TbItemMagico |
| `renome` | `nome` (nunca `slug`) | 125 | TbItemMagico |
| `limpar_dados_oficiais` | `descricao_markdown` | 302 | TbItemMundano |
| `preencher_kit_inicial_html` (+1 correção) | `equipamento` | 11 | TbClasse |
| `add_pick_estilos_de_ki_2_5_11_17` | `tags_json` | 1 | TbClassehabilidade (pk1505) |
| rechaço → retaliação (remap) | `tags_json` + `descricao` | 2 | TbClassehabilidade (pk909) |
| `delete_acesso_base_monge_erroneo_estilos_kensei` | (row) | 1 → **9 linhas** | TbAcessoopcao |

Detalhamento:

1. **Itens mágicos (TbItemMagico, UPSERT por slug ESTÁVEL):** 953 itens tiveram `tags_json`
   enxutas (metadados removidos), 470 descrições reformatadas e 125 renomes. **Os renomes tocam
   só o campo `nome` — o `slug` não muda**, então o merge por slug atualiza a linha existente na
   prod (sem duplicar / sem órfão). Inclui o **escudo pk=7 `+1 Escudo (*)`** com
   `tags_json=['ca:+3']` (era `ca:+1`: um escudo comum já daria +2, então o +1 mágico 5e vira
   **+3** na forma consumida `escudo_bonus`; CA do Scar **19 → 20** casando a planilha).
   **Nesta versão** o mesmo critério corrige os outros dois escudos mágicos: **pk20 `+2 Escudo (*)`
   → `ca:+4`** e **pk32 `+3 Escudo (*)` → `ca:+5`** (antes `ca:+2`/`ca:+3`, que subestimavam a CA por
   ignorar o +2 base do escudo comum).
2. **Itens mundanos (TbItemMundano, SUBSTITUI):** 302 descrições limpas. Contagem intacta (302).
3. **Kits de equipamento (TbClasse, UPSERT por slug):** campo `equipamento` preenchido nas 13
   classes (10 via HTML + Bárbaro/Mago existentes + **1 correção pontual do Místico**: kit A/B com
   Besta Leve, Foco Arcano, Pacote de Erudito, Couro, 2 Adagas, ou 150 PO). Contagem intacta (13).
4. **Ki do Monge corrigido:** `pick:opcao:estilos_de_ki` nos níveis **2/5/11/17** em
   TbClassehabilidade (Monge/Ki, pk1505) **+ DELETE de 9 TbAcessoopcao** base-Monge **errôneos**
   dos estilos Kensei (pks `80,82,84,86,88,90,92,94,96`). Os estilos Kensei seguem acessíveis
   **só via sub=Kensei N3** (acesso correto preservado). → **TbAcessoopcao 97 → 88 (−9)**.
5. **Rechaço (Magiduelista, TbClassehabilidade pk909):** `spell_selection:rechaco` referenciava
   magia **ausente**. Rechaço = *backlash* = **Retaliação**, que **já existe** em TbMagia pk=33
   slug=`retaliacao`. Foi **REMAP da referência** (`rechaco` → `retaliacao`) + link na descrição.
   **NÃO houve importação** — TbMagia continua **580** (0 inseridas).
6. **SCHEMA (migração 0063):** `TbMagia` **perdeu o campo `subclasses`**. Os 580 registros têm os
   **mesmos PKs** e o **mesmo conteúdo** (0 mudanças de valor ignorando `subclasses`); só o
   `sha256_registros` muda por causa da coluna removida.

## Diff de contagens vs report do 20260719_200533 — explicação de CADA linha

**Δ de LINHAS em apenas UMA tabela; TbMagia NÃO variou (rechaço foi remap, não import).**

| Tabela | Ação | Prod antes (200533) | Neste arquivo / pós | Δ linhas | Explicação |
|---|---|---:|---:|---:|---|
| TbRaca | upsert_slug | 4 | 4 | 0 | — |
| TbLinhagem | upsert_slug | 16 | 16 | 0 | — |
| TbEssencia | upsert_slug | 4 | 4 | 0 | — |
| TbAntecedente | upsert_slug | 30 | 30 | 0 | — |
| TbClasse | upsert_slug | 13 | 13 | 0 | valor: kits em 13 |
| TbSubclasse | upsert_slug | 111 | 111 | 0 | — |
| TbOpcaojogo | upsert_slug | 259 | 259 | 0 | estilos_de_ki já existiam |
| **TbMagia** | upsert_slug | 580 | **580** | **0** | rechaço **remapeado** p/ retaliacao pk=33 (NÃO importado). Schema: −campo `subclasses` |
| TbTalento | upsert_slug | 139 | 139 | 0 | — |
| TbItemMagico | upsert_slug | 953 | 953 | 0 | valor: 953 tags + 470 desc + 125 nome + escudo |
| TbCosmetico | upsert_slug | 24 | 24 | 0 | — |
| TbClassehabilidade | substitui | 884 | 884 | 0 | valor: pk909 (remap) + pk1505 (ki pick) |
| TbRecursoclasse | substitui | 135 | 135 | 0 | — |
| **TbAcessoopcao** | substitui | 97 | **88** | **−9** | **DELETE de 9 acessos base-Monge errôneos dos estilos Kensei** (Ki do Monge corrigido) |
| TbTracoracial | substitui | 352 | 352 | 0 | — |
| TbCondicao | substitui | 28 | 28 | 0 | — |
| TbIdioma | substitui | 22 | 22 | 0 | — |
| TbRegra | substitui | 139 | 139 | 0 | — |
| TbRecompensaMestre | substitui | 9 | 9 | 0 | — |
| TbItemMundano | substitui | 302 | 302 | 0 | valor: 302 descrições limpas |
| TbBestiario | substitui | 920 | 920 | 0 | — |
| TbConquista / TbArmadilha | 0 → ausente | — | preservado | — | 0 linhas no dev |
| TbRegiao / TbTerritorio / TbMapMarker / TbMapDesenho | skip/preserva | — | 74/35/74/1 | fora | mundo/mapa — prod vence |
| TbOrganizacao / TbMapLayer | fora do sync | — | 81 / 4 | fora | nunca tocados |

**Total no arquivo: 5012 registros / 21 modelos** (baseline 5021; **−9 = os 9 acessos Kensei**).
`inserted=0` em toda tabela; `removed=9` só em TbAcessoopcao. **Nenhum diff inexplicado.**

**Tabelas com `sha256_registros` ALTERADO vs 200533 (6):**

| Tabela | Natureza | sha256_registros (novo) |
|---|---|---|
| TbItemMagico | valor (tags/desc/nome/escudos +1/+2/+3) | `516eacc98e9809ae0bb7825e272b54fd0948d94c0e964dcf8b16e57fec7727ab` |
| TbItemMundano | valor (descrições) | `8d4c5d2d997063be89ecfae3b6de93093ec74766a1ff1eda8190cbec7e0d7a93` |
| TbClasse | valor (kits) | `53e8a7ae1050a0ce940f075166f0167e30d9a5135ca8cf22628ae4ad07a21c24` |
| TbClassehabilidade | valor (pk909 + pk1505) | `df11b95fb118960c0b8165c036ac5b3770a1b042ce5e60f1a09dbaecb1c4a957` |
| TbAcessoopcao | **linhas (−9)** | `e804b9e4c7303d63c3f1f1c0d52a6c36ab7de0c9c5e5eab4475d5537d4dd414d` |
| TbMagia | **schema (−`subclasses`)** | `52f6669c74f98fcab88b73105610ddf127fffe2ec9f9cfaffd2a9fce8840ec21` |

As outras **15 tabelas com linhas batem `sha256_registros` EXATAMENTE** com o report do 200533.

## Validação já executada (independente)

`json.load` → `deserialize` completo → aplicação em `transaction.atomic()` **revertida (rollback)**
sobre o próprio `db.sqlite3` do dev — **nada persistido** (pré == pós confirmado):

- **Bytes em disco:** SHA-256 do arquivo == `sha256_arquivo` do report (**match**). CRLF puro
  (233162 linhas CRLF, **0** LF solto).
- **`json.load`:** 5012 registros == `final_records`. **`deserialize`:** 5012 objetos, 21 modelos.
- **Memória intacta:** `mem_ok=True`, 21 tabelas de usuário/missão com contagem pré == pós.
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` entram em `pass2_skipped`
  (junto de `TbArmadilha`); contagens antes/depois idênticas (**74/35/74/1**).
- **SUBSTITUI reinseriu a contagem exata do dev** (TbAcessoopcao reinserido = **88**); todos os
  UPSERT casaram por slug.

Spot-checks no fixture (bytes em disco):

- **Kit do Místico** (TbClasse pk11 `equipamento`): presente, contém `Besta Leve` e `150 PO`.
- **Item renomeado** (TbItemMagico pk14 `nome`): `+1 Bastão do Guardião do Pacto`.
- **Escudos** (TbItemMagico): pk7 `+1 Escudo (*)` `['ca:+3']`, pk20 `+2 Escudo (*)` `['ca:+4']`,
  pk32 `+3 Escudo (*)` `['ca:+5']`.
- **TbMagia SEM `subclasses`**: 580 registros, **0** com o campo `subclasses`.
- **Rechaço** (TbClassehabilidade pk909): `retaliacao` presente, `rechaco` ausente.
- **Estilos de Ki** (TbClassehabilidade pk1505): `estilos_de_ki` presente.
- **Acessos Kensei** ausentes do fixture (pks 80/82/84/86/88/90/92/94/96).

---

## CHECKLIST DO DEPLOY ÚNICO (ordem obrigatória)

> ⚠️ **A ORDEM IMPORTA — o schema mudou (0063).** As migrações têm de rodar **ANTES** do merge.

### 1. `force_update.bat` — PRIMEIRO

Roda as migrações **0061 → 0062 → 0063** em produção **ANTES** de qualquer merge. A **0063**
remove a coluna `subclasses` de `TbMagia`; se o merge rodar antes, o `loaddata`/deserialize dos
580 registros (que **não** têm mais `subclasses`) bate com um schema antigo que ainda espera a
coluna. **Rode o `force_update.bat` e confirme que as três migrações aplicaram sem erro.**

### 2. Baixe o backup completo pelo console

Ação **"Baixar backup"** (`download_backup_view`) do admin. **Guarde-o** — é o rollback real do
momento, tirado **depois** das migrações.

### 3. Merge de conteúdo com o `restore_20260720_060551.json`

No console do admin, ação **"Merge de conteudo (dev -> producao)"** (`action=merge_conteudo`),
**NÃO** "Restauração de backup". Faça upload do `restore_consolidado_20260720_152950.json` **subido
do disco do dev** (`ref/backups/`, gitignored — não está no repositório).

> O painel "Restaurar backup" (upsert por PK) **FALHA** com este fixture (colisão de slug único —
> PKs de dev/prod desalinhados); o guard em `home/admin.py` recusa. Use **exclusivamente o merge
> por slug**. Ele faz UPSERT por slug (preserva PK), SUBSTITUI (delete+reinsert), pula os modelos
> ausentes (mapa/mundo) e roda `sqlsequencereset` no fim (PASSO 3, só Postgres).

**Leia o relatório na tela:** deve terminar com "MEMÓRIA INTACTA: 21 tabelas…" e listar
`TbRegiao/TbTerritorio/TbMapMarker/TbArmadilha/TbMapDesenho` em "Tabelas preservadas por ausência
no fixture". **Confira as contagens** contra a coluna "Neste arquivo / pós" acima — em especial
**`home.tbacessoopcao` = 88** (era 97) e **`home.tbmagia` = 580**. Se disser "ATENÇÃO: memória
mudou!", **pare** e faça rollback.

### 4. Rollback (se algo sair errado)

Ação **"Restauração de backup"** com upload do backup do **passo 2** (preferível) ou, na falta,
`ref/Characterbuilder testes/backup_completo_20260718_015031.json`. Faz upsert por PK + realinha
sequences, revertendo só o catálogo (memória e mapa não foram tocados).

### 5. PÓS-DEPLOY MANUAL — trocar o escudo equipado do Scar

O inventário do Scar em **produção aponta um escudo comum** (isso é **memória de personagem** — o
deploy **não** toca). Depois do merge, **troque manualmente** o escudo equipado do Scar pelo item
**`+1 Escudo (*)`** (TbItemMagico pk7, `ca:+3`). Feita a troca, a **CA do Scar vira 20**, casando
a planilha (`LOG!R12`).

### 6. Smoke test (invariantes reais do espelho Scar)

- **Manopla** → **FOR 19**.
- **Ataque desarmado**: **+11** para acertar / dano **`1d10 +7`**.
- **Velocidade**: **50 ft**.
- **Metamagia**: pontos **2 / 4 / 6** (progressão).
- **Estilos de luta** ativos (Arquearia `ranged.atk:+2`, Defesa `armor.ca:+1`, etc.).
- **Fúrias = Bônus de Proficiência** (recurso por fórmula `{1:pb}`).
- **Mercado de Mestre** com preços renderizando.
- **Level-up sem reload** (aplica nível/subclasse/ASI e a ficha atualiza sem recarregar).

---

## Decisões do PO ainda pendentes (herdadas)

1. **Mapa/mundo/organizações:** confirmar **PROD VENCE** e retirar `TbRegiao/TbTerritorio/
   TbMapMarker/TbMapDesenho` da lista `SUBSTITUI` em `home/deploy_sync.py` (hoje só ficam a salvo
   por estarem ausentes do fixture — tarefa à parte, este pacote não mexe no `deploy_sync.py`).
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Fora.
3. **`TbConquista` vazia no dev (0)** apesar do seed 0052 — popular antes se o catálogo deve existir.
