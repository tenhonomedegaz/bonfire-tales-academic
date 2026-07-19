# Restore de conteúdo prod (dev-vence) — 2026-07-19 03:43:04

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260719_034304.json` (5021 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260719_034304.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF):** `1da49bc52c166721b2783b2d457bbef36df09ba90507506cab9de31512fd38b0`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise / prod de referência:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json` (backup fresco da prod).
- **Rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
- **Substitui:** `restore_consolidado_20260718_054605.json` (mesmo conjunto de 21 modelos; **uma linha a mais** — nova condição `doente` — e valores de tag re-taggeados pela remodelagem R2 em 5 tabelas).

## O que mudou nesta versão (vs 20260718_054605)

Esta versão captura a **remodelagem R2** do catálogo do dev — **341 aplicações de tag**
registradas em `log_aplicacao_r2.jsonl` — mais **1 condição nova**. Por `achado`:

1. **246 `R2-magia-slug`** — slugs de magia normalizados de `underscore` para `hífen`
   (`bola_de_fogo` → `bola-de-fogo`) e **referências quebradas remapeadas** (equivalentes
   EN→PT, ex.: `charm_person`/`command` → `enfeiticar-pessoa`/`comando`, e duplicadas
   resolvidas). Afeta tags de habilidades, traços, talentos, opções e classes.
2. **91 `R2-estrutural`** — ajustes estruturais de tag (modos de ativação e correções de
   forma), incluindo uma remoção parcial segura de lixo em `TbClassehabilidade#971`.
3. **3 `R2-rename`** — renomeações em `TbClassehabilidade` (#611, #625, #1206).
4. **1 `R2-condicao-doente`** — **nova `TbCondicao` `doente`** (slug `doente`):
   `TbCondicao` 27 → **28**. É a **única mudança de contagem de linhas** da rodada.

Tabelas com **valor de tag alterado** (mesma contagem de linhas) — número de aplicações R2:
`TbClassehabilidade` 132, `TbTracoracial` 127, `TbTalento` 60, `TbOpcaojogo` 19, `TbClasse` 2.
Prova de integridade: os `sha256_registros` das **15 tabelas restantes** batem **exatamente**
com os do report de 20260718_054605 — só estas 6 (as 5 acima + `TbCondicao`) mudaram.

Nenhuma outra linha nova/removida e nenhum outro campo alterado nos 21 modelos.

## O que este arquivo faz

Empurra o **catálogo de conteúdo** do dev para a produção (dev vence), do jeito exato da
classificação em `home/deploy_sync.py`:

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento, TbItemMagico,
  TbCosmetico`. Casa por `slug`, atualiza os campos, mantém o ID que os dados de usuário
  referenciam. Insere os que não existem. (`TbConquista` está na lista mas tem 0 linhas no
  dev → ausente do fixture.)
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade,
  TbRecursoclasse, TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra,
  TbRecompensaMestre, TbItemMundano, TbBestiario`. (`TbArmadilha` está na lista mas tem 0
  linhas → ausente do fixture → tabela preservada na prod.)

**O que NÃO está no arquivo (de propósito):** `TbRegiao, TbTerritorio, TbMapMarker,
TbMapDesenho` (estão em `CONTENT_MODELS`/`SUBSTITUI`, mas foram **EXCLUÍDOS** explicitamente
do fixture), além de `TbOrganizacao` e `TbMapLayer` (que nem entram em nenhuma lista de sync)
e toda a **memória** (usuários, personagens, transações, tabelas do bot). Como o aplicador
`sincronizar_conteudo` **pula (e preserva) qualquer modelo ausente no fixture**, o mapa/mundo
e as 81 organizações da staff na produção ficam **intactos**. A memória nunca é tocada.

## Números por tabela (dev-vence)

| Tabela | Ação | No arquivo | Prod depois (esperado) |
|---|---|---:|---:|
| TbRaca | upsert_slug | 4 | 4 |
| TbLinhagem | upsert_slug | 16 | 16 |
| TbEssencia | upsert_slug | 4 | 4 |
| TbAntecedente | upsert_slug | 30 | 30 |
| TbClasse | upsert_slug | 13 | 13 |
| TbSubclasse | upsert_slug | 111 | 111 |
| TbOpcaojogo | upsert_slug | 259 | 259 |
| TbMagia | upsert_slug | 580 | 580 |
| TbTalento | upsert_slug | 139 | 139 |
| TbItemMagico | upsert_slug | 953 | 953 |
| TbCosmetico | upsert_slug | 24 | 24 |
| TbClassehabilidade | substitui | 884 | 884 |
| TbRecursoclasse | substitui | 135 | 135 |
| TbAcessoopcao | substitui | 97 | 97 |
| TbTracoracial | substitui | 352 | 352 |
| **TbCondicao** | **substitui** | **28** | **28** |
| TbIdioma | substitui | 22 | 22 |
| TbRegra | substitui | 139 | 139 |
| TbRecompensaMestre | substitui | 9 | 9 |
| TbItemMundano | substitui | 302 | 302 |
| TbBestiario | substitui | 920 | 920 |
| **TbRegiao** | **skip/preserva** | — | **74** |
| **TbTerritorio** | **skip/preserva** | — | **35** |
| **TbMapMarker** | **skip/preserva** | — | **74** |
| **TbMapDesenho** | **skip/preserva** | — | **1** |
| **TbOrganizacao** | **fora do sync** | — | **81** |
| **TbMapLayer** | **PO decide** | — | **4** |
| TbConquista / TbArmadilha | 0 linhas → ausente | — | preservado |

Total no arquivo: **5021 registros / 21 modelos** — mesmo conjunto de 21 modelos do
`restore_consolidado_20260718_054605`, com **1 registro a mais** (condição `doente`).

## Validação já executada

Apliquei o arquivo via `sincronizar_conteudo` numa **transação revertida (rollback)** sobre o
próprio `db.sqlite3` do dev — nenhuma linha foi persistida (confirmado: contagem pré == pós):

- **Memória intacta:** 21 tabelas de usuário/missão com a mesma contagem (`mem_ok=True`).
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` entram em
  `pass2_skipped` (junto de `TbArmadilha`) = "modelo ausente no fixture; tabela preservada".
  Contagens antes/depois idênticas (74/35/74/1).
- Todos os SUBSTITUI reinseriram a contagem exata do dev; todos os UPSERT casaram por slug
  (0 inseridos, todos atualizados — prod = subset por slug).
- Os `sha256_registros` das **15 tabelas não tocadas pela R2** batem exatamente com os do
  report de 20260718_054605 (prova de que só `TbClasse`, `TbClassehabilidade`, `TbTracoracial`,
  `TbTalento`, `TbOpcaojogo` e `TbCondicao` mudaram).

Spot-checks no fixture (bytes em disco):

- `TbCondicao` — slug `doente` **presente** (28 condições no total).
- `TbClassehabilidade[638]` — `tag_depois` do log presente: `spell:pick{[enfeiticar-pessoa, comando]}`.
- `TbOpcaojogo[144]` — slug hifenizado `armadura-arcana` presente.
- `TbTalento[8]` — slug hifenizado `chama-sagrada` presente.

## Como aplicar na PRODUÇÃO (passo a passo)

1. **Baixe um backup fresco da produção AGORA** pelo admin (`download_backup_view`). Guarde-o:
   é o rollback real do momento. O rollback base desta rodada é
   `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
2. No **console do admin**, use a ação **"Merge de conteudo (dev -> producao)"**
   (`action=merge_conteudo`), **NÃO** a **"Restauração de backup"**. Faça upload de
   `ref/backups/restore_consolidado_20260719_034304.json`.

   > ⚠️ **AVISO — use EXCLUSIVAMENTE o painel "Merge de conteudo (dev -> producao)" para este
   > arquivo.** O painel "Restaurar backup" (upsert por PK) **FALHA** com este fixture — colisão
   > de slug único (`spells_Slug_key`) — porque os PKs do dev e da produção estão desalinhados.
   > Foi o erro observado em produção em 16/07/2026. O guard em `home/admin.py` recusa esse upload
   > automaticamente, mas a ação correta continua sendo o merge por slug.
   - Esse fluxo chama `home.deploy_sync.sincronizar_conteudo`: UPSERT por slug (preserva PK),
     SUBSTITUI (delete+reinsert), pula os modelos ausentes (mapa/mundo) e roda `sqlsequencereset`
     no fim (PASSO 3, realinha as sequences do Postgres).
3. **Leia o relatório na tela.** Ele deve dizer, no fim, "MEMÓRIA INTACTA: 21 tabelas…" e listar
   `TbRegiao/TbTerritorio/TbMapMarker/TbArmadilha/TbMapDesenho` em "Tabelas preservadas por
   ausência no fixture". Se disser "ATENÇÃO: memória mudou!", **pare** e faça rollback.
4. **Confira as contagens** contra a coluna "Prod depois (esperado)" da tabela acima (e contra
   `final_counts`/`por_tabela` no `.report.json`). Em especial, `home.tbcondicao` deve ficar
   em **28** (com a condição `doente`) e `home.tbitemmagico` em **953**.

## Plano de rollback

- Se algo sair errado, use a ação **"Restauração de backup"** do console e faça upload do backup
  de produção — de preferência o que você baixou no passo 1; na falta dele,
  `ref/Characterbuilder testes/backup_completo_20260718_015031.json`. Ela faz
  `deserialize().save()` (upsert por PK) e realinha sequences, revertendo o catálogo ao estado do
  backup. Como a memória e o mapa **não foram tocados** por este restore, o rollback afeta só o
  catálogo.

## Aguardando decisão do PO

1. **Mapa / mundo / organizações:** confirmar **PROD VENCE** e **retirar `TbRegiao, TbTerritorio,
   TbMapMarker, TbMapDesenho` da lista `SUBSTITUI` em `home/deploy_sync.py`**. Hoje eles só ficam
   a salvo porque estão AUSENTES deste fixture. **Este arquivo não corrige o `deploy_sync.py` — é
   tarefa à parte.**
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Ficou fora.
3. **`TbConquista` vazia no dev (0)** apesar da migração `0052_seed_conquistas`. Se o catálogo de
   conquistas deve existir em prod, **popular o dev e regerar** antes de aplicar (senão vai como 0).
