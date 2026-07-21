# Restore de conteúdo prod (dev-vence) — 2026-07-21 00:06:06 — PÓS-BETA DA STAFF (sintonias, homebrew, avental, brigão/luchador)

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260721_000606.json` (5012 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260721_000606.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF puro):** `2fbfa6dec9bcc77b47e5ff5eb168442eb970e15e825eba62f3070a1b8fbca9dc`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise (baseline):** `restore_consolidado_20260720_152950.json` — **esta versão o supersede**.
- **Rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json` (restore_backup por PK) ou o backup fresco do passo 2 abaixo.

> **POLÍTICA DE ENTREGA (PO):** o `.json` e o `.report.json` ficam **SÓ NO DISCO** em
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

## O que mudou nesta versão (vs baseline `20260720_152950`)

**SÓ mudança de VALOR em 2 tabelas; 0 mudança de LINHA em todas as 21** — as contagens são
idênticas ao 152950 (5012 registros). Foram **18 registros** de valor:

### TbItemMagico — 16 registros (UPSERT por slug)

| Grupo | Nº | pks | Natureza |
|---|---:|---|---|
| **Sintonizações puras** | **13** | `538, 539, 896, 897, 903, 913, 914, 920, 925, 932, 934, 942, 944` | apenas o campo `requer_sintonizacao` foi ajustado (true↔false), nada mais |
| **Avental (slug novo)** | 1 | `164` | `nome` **Babador de açougueiro → Avental de Açougueiro** e `slug` `babador-de-acougueiro → avental-de-acougueiro` |
| **Distintivo (homebrew)** | 1 | `331` | `requer_sintonizacao` true→false, `tags_json` `["consumable","ca:+2"] → ["ca:+2"]` (remove `consumable`), nota "regra da casa" na descrição |
| **Adaga (homebrew)** | 1 | `45` | `tags_json` `blindsight(30ft) → blindsight(15ft)`, `requer_sintonizacao` true→false (sintonização opcional), descrição de regra da casa |

> **Avental — atenção ao slug.** O rename toca `nome` **e** `slug`. No dev é a **mesma linha**
> (0 linha nova). No merge por slug, a prod recebe a linha **`avental-de-acougueiro`** como
> **INSERT** (slug ausente na prod) e a antiga **`babador-de-acougueiro`** fica **órfã** (o merge
> não deleta o que não está no fixture; não há tombstone). Se o item antigo ainda estiver em algum
> inventário de personagem, ele continua válido; a limpeza da linha órfã é **manual** (opcional).
> As outras 15 alterações de item são UPSERT estável (slug inalterado) — atualizam a linha da prod.

### TbTalento — 2 registros (UPSERT por slug)

- **pk3 `Brigão de Taverna`** e **pk49 `Luchador`** — `tags_json` re-taggeadas para o vocabulário
  novo (`always_active{ unarmed_strike.dmg:=1d6+str_mod(concussao) }` +
  `while_active{ trigger=hit{unarmed}, ... }`), substituindo a forma antiga com `if()` inline. **0
  linha nova.**

## Diff de contagens vs report do `20260720_152950` — explicação de CADA linha

**Δ de LINHAS = 0 em TODAS as 21 tabelas.** Só há Δ de VALOR (mesma contagem) em duas.

| Tabela | Ação | Prod/baseline (152950) | Neste arquivo / pós | Δ linhas | Explicação |
|---|---|---:|---:|---:|---|
| TbRaca | upsert_slug | 4 | 4 | 0 | — |
| TbLinhagem | upsert_slug | 16 | 16 | 0 | — |
| TbEssencia | upsert_slug | 4 | 4 | 0 | — |
| TbAntecedente | upsert_slug | 30 | 30 | 0 | — |
| TbClasse | upsert_slug | 13 | 13 | 0 | — |
| TbSubclasse | upsert_slug | 111 | 111 | 0 | — |
| TbOpcaojogo | upsert_slug | 259 | 259 | 0 | — |
| TbMagia | upsert_slug | 580 | 580 | 0 | — |
| **TbTalento** | upsert_slug | 139 | 139 | **0** | **valor: pk3 Brigão + pk49 Luchador re-tag** |
| **TbItemMagico** | upsert_slug | 953 | 953 | **0** | **valor: 13 sintonias + Avental(164) + Distintivo(331) + Adaga(45)** |
| TbCosmetico | upsert_slug | 24 | 24 | 0 | — |
| TbClassehabilidade | substitui | 884 | 884 | 0 | — |
| TbRecursoclasse | substitui | 135 | 135 | 0 | — |
| TbAcessoopcao | substitui | 88 | 88 | 0 | — |
| TbTracoracial | substitui | 352 | 352 | 0 | — |
| TbCondicao | substitui | 28 | 28 | 0 | — |
| TbIdioma | substitui | 22 | 22 | 0 | — |
| TbRegra | substitui | 139 | 139 | 0 | — |
| TbRecompensaMestre | substitui | 9 | 9 | 0 | — |
| TbItemMundano | substitui | 302 | 302 | 0 | — |
| TbBestiario | substitui | 920 | 920 | 0 | — |
| TbConquista / TbArmadilha | 0 → ausente | — | preservado | — | 0 linhas no dev |
| TbRegiao / TbTerritorio / TbMapMarker / TbMapDesenho | skip/preserva | — | 74/35/74/1 | fora | mundo/mapa — prod vence |
| TbOrganizacao / TbMapLayer | fora do sync | — | 81 / 4 | fora | nunca tocados |

**Total no arquivo: 5012 registros / 21 modelos** (idêntico ao 152950). `inserted=0`, `removed=0`
em toda tabela. **Nenhum diff de linha; nenhum diff inexplicado.**

**Tabelas com `sha256_registros` ALTERADO vs 152950 (apenas 2):**

| Tabela | Natureza | sha256_registros (novo) |
|---|---|---|
| TbItemMagico | valor (13 sintonias + avental + distintivo + adaga) | `b49e3bd7c6b7f47e7c13974074974f56c4174e923f00bee89952e98bcc4b24c2` |
| TbTalento | valor (brigão + luchador) | `2f9ef6ced2281d58950b14ea7accc5de68667c2010a1562464dc5729f606b43e` |

As outras **19 tabelas com linhas batem `sha256_registros` EXATAMENTE** com o report do 152950.

## Validação já executada (independente)

`json.load` → `deserialize` completo → aplicação em `transaction.atomic()` **revertida (rollback)**
sobre o próprio `db.sqlite3` do dev — **nada persistido** (pré == pós confirmado):

- **Bytes em disco:** SHA-256 do arquivo == `sha256_arquivo` do report (**match**). CRLF puro
  (233163 pares CRLF, **0** LF solto), **sem BOM**, UTF-8 cru.
- **`json.load`:** 5012 registros == `final_records`. **`deserialize`:** 5012 objetos, 21 modelos.
- **Memória intacta:** `mem_ok=True`; contagem pré == pós tanto na memória quanto no conteúdo.
- **Mapa preservado:** `pass2_skipped = [TbRegiao, TbTerritorio, TbMapMarker, TbArmadilha,
  TbMapDesenho]` — mundo/mapa entram por **ausência** no fixture (prod vence).

Spot-checks no fixture (bytes em disco):

- **Avental** (TbItemMagico): `avental-de-acougueiro` **presente** (`Avental de Açougueiro`);
  `babador-de-acougueiro` **ausente** do fixture.
- **Distintivo** (pk331): `requer_sintonizacao=false` e **sem** `consumable` nas tags.
- **Adaga** (pk45): tags com `blindsight(15ft)`.
- **3 das 13 sintonias:** pk538 `Maça da Destruição` = `true` (era false); pk920 `Juiz dos Magos`
  = `false` (era true); pk932 `Sono do Corvo` = `false` (era true).

---

## CHECKLIST DO DEPLOY (ordem obrigatória)

> **Este é um restore CONSOLIDADO (dev-vence, catálogo inteiro).** Se o deploy anterior
> (`152950` / `060551`) **ainda não foi aplicado** na prod, **este arquivo engloba tudo** — basta
> **UM merge só** (ele carrega todo o cumulativo: escudos +1/+2/+3, kits, ki, itens, e agora as
> sintonias/homebrew/avental/brigão-luchador). Não é preciso aplicar os anteriores antes.

### 1. `force_update.bat` — PRIMEIRO

Roda as migrações em produção **ANTES** de qualquer merge (inclui **0063** que remove a coluna
`subclasses` de `TbMagia`, necessária porque os 580 registros do fixture não têm mais esse campo, e
**0064** que adiciona `concedido_por`/`concedido_em`/`origem_nota` a `TbPersonagemItem` para o
painel de itens de missão da staff). **Confirme que todas aplicaram sem erro.**

### 2. Baixe o backup completo pelo console

Ação **"Baixar backup"** (`download_backup_view`) do admin. **Guarde-o** — é o rollback real do
momento, tirado **depois** das migrações.

### 3. Merge de conteúdo com o `restore_consolidado_20260721_000606.json`

No console do admin, ação **"Merge de conteudo (dev -> producao)"** (`action=merge_conteudo`),
**NÃO** "Restauração de backup". Faça upload do `restore_consolidado_20260721_000606.json` **subido
do disco do dev** (`ref/backups/`, gitignored — não está no repositório).

> O painel "Restaurar backup" (upsert por PK) **FALHA** com este fixture (colisão de slug único —
> PKs de dev/prod desalinhados); o guard em `home/admin.py` recusa. Use **exclusivamente o merge
> por slug**. Ele faz UPSERT por slug (preserva PK), SUBSTITUI (delete+reinsert), pula os modelos
> ausentes (mapa/mundo) e roda `sqlsequencereset` no fim (PASSO 3, só Postgres).

**Leia o relatório na tela:** deve terminar com "MEMÓRIA INTACTA: 21 tabelas…" e listar
`TbRegiao/TbTerritorio/TbMapMarker/TbArmadilha/TbMapDesenho` em "Tabelas preservadas por ausência
no fixture". **Confira as contagens** — todas idênticas ao 152950 (ex.: `home.tbitemmagico=953`,
`home.tbtalento=139`, `home.tbacessoopcao=88`, `home.tbmagia=580`). Se disser "ATENÇÃO: memória
mudou!", **pare** e faça rollback.

### 4. Rollback (se algo sair errado)

Ação **"Restauração de backup"** com upload do backup do **passo 2** (preferível) ou, na falta,
`ref/Characterbuilder testes/backup_completo_20260718_015031.json`. Faz upsert por PK + realinha
sequences, revertendo só o catálogo (memória e mapa não foram tocados).

### 5. Pós-deploy (opcional) — linha órfã do Avental

O merge insere `avental-de-acougueiro` e **não** remove `babador-de-acougueiro` (sem tombstone).
Se quiser, remova manualmente a linha órfã na prod **depois** de confirmar que nenhum inventário de
personagem ainda a referencia (é memória de personagem — o deploy não toca).

---

## Decisões do PO ainda pendentes (herdadas)

1. **Mapa/mundo/organizações:** confirmar **PROD VENCE** e retirar `TbRegiao/TbTerritorio/
   TbMapMarker/TbMapDesenho` da lista `SUBSTITUI` em `home/deploy_sync.py` (hoje só ficam a salvo
   por estarem ausentes do fixture — tarefa à parte, este pacote não mexe no `deploy_sync.py`).
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Fora.
3. **`TbConquista` vazia no dev (0)** apesar do seed 0052 — popular antes se o catálogo deve existir.
