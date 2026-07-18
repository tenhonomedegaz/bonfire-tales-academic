# Restore de conteúdo prod (dev-vence) — 2026-07-18 05:46:05

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260718_054605.json` (5020 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260718_054605.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF):** `ea2afe7e497e37164c026e48f1e45701fa3d4c53020a550c9bc6004471714cbc`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise / prod de referência:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json` (backup fresco da prod).
- **Rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
- **Substitui:** `restore_consolidado_20260717_155113.json` (mesmo conjunto de 21 modelos; **uma linha a menos** — item mágico 718 removido — e valores de campo de 6 registros).

## O que mudou nesta versão (vs 20260717_155113)

O diff completo (registro a registro) entre o restore vigente e este é **apenas**:

1. **`TbItemMagico` id=548 "Manoplas do Poder do Ogro"** — `tags_json` re-taggeada com
   `attr_set:str_score=19` (piso de Força 19).
2. **`TbClasse` skills_lvl1 normalizadas em 4 classes** — Bárbaro (pk 3), Caçador (pk 4),
   Druida (pk 6) e Guerreiro (pk 8): `adestrar_animais` → `adestrar-animais`. Provado
   que a única diferença de cada `tags_json` é essa troca de `_` por `-` (strings idênticas
   após normalizar).
3. **`TbItemMagico` id=718 "Poção de Cura (\*)" (slug `pocao-de-cura-2`) DELETADA** —
   954 → **953** itens mágicos. É a única mudança de **contagem de linhas** da rodada.
4. **`TbClassehabilidade` id=967 "Conhecimento Primitivo"** — `tags_json` ajustada de
   `pick:pericia:{classlvl=5:1, classlvl=10:2}` para `pick:pericia:{classlvl=5:1, classlvl=10:1}`
   (no nível 10 passa a escolher **1** perícia em vez de 2).

> ⚠️ **A mudança nº 4 NÃO constava do escopo enunciado desta rodada** (que citava só as
> mudanças 1–3). Ela é uma alteração **real** do catálogo do dev — confirmada no `db.sqlite3`
> live — que aconteceu depois do restore de 17/07 (provavelmente durante o trabalho de
> `pick:pericia`). Como este arquivo reflete o **estado atual do dev** (política dev-vence),
> a mudança entra no fixture automaticamente. Está listada aqui para transparência; se o PO
> **não** quiser propagar essa alteração agora, é preciso reverter o `tags_json` do id=967 no
> dev e **regerar** antes de aplicar em produção.

Nenhuma outra linha nova/removida e nenhum outro campo alterado em nenhum dos 21 modelos.

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

> **Deleção do item 718:** o merge por slug **não deleta sozinho** slugs que sumiram do dev —
> ele faz UPSERT dos presentes e preserva os ausentes. Como `TbItemMagico` é UPSERT_POR_SLUG,
> o slug `pocao-de-cura-2` que ainda existir na prod **NÃO é removido** só por não estar no
> fixture. A remoção efetiva em produção depende de tombstone em `home/content_deletions.json`
> (mecanismo PASSO 2.5 do `sincronizar_conteudo`) **ou** de deleção manual pelo admin. Verifique
> se o fluxo de deleção desejado inclui esse tombstone; este arquivo, por si só, apenas **deixa
> de conter** o item.

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
| TbItemMagico | upsert_slug | **953** | **953** |
| TbCosmetico | upsert_slug | 24 | 24 |
| TbClassehabilidade | substitui | 884 | 884 |
| TbRecursoclasse | substitui | 135 | 135 |
| TbAcessoopcao | substitui | 97 | 97 |
| TbTracoracial | substitui | 352 | 352 |
| TbCondicao | substitui | 27 | 27 |
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

Total no arquivo: **5020 registros / 21 modelos** — mesmo conjunto de 21 modelos do
`restore_consolidado_20260717_155113`, com **1 registro a menos** (item mágico 718).

## Validação já executada

Apliquei o arquivo via `sincronizar_conteudo` numa **transação revertida (rollback)** sobre o
próprio `db.sqlite3` do dev — nenhuma linha foi persistida (confirmado: contagem pré == pós):

- **Memória intacta:** 21 tabelas de usuário/missão com a mesma contagem (`mem_ok=True`).
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` entram em
  `pass2_skipped` (junto de `TbArmadilha`) = "modelo ausente no fixture; tabela preservada".
  Contagens antes/depois idênticas (74/35/74/1).
- Todos os SUBSTITUI reinseriram a contagem exata do dev; todos os UPSERT casaram por slug
  (0 inseridos, todos atualizados — prod = subset por slug).
- Além disso, os `sha256_registros` das **19 tabelas não alteradas** batem exatamente com os do
  report de 17/07 (prova de que só `TbClasse`, `TbClassehabilidade` e `TbItemMagico` mudaram).

Spot-checks no fixture (bytes em disco):

- `TbItemMagico[548]` (Manoplas) — `tags_json` contém `attr_set:str_score=19`.
- `TbClasse[barbaro].tags_json` — `skills_lvl1` com `adestrar-animais` (hífen); `adestrar_animais`
  (underscore) ausente. Idem cacador/druida/guerreiro.
- slug `pocao-de-cura-2` **AUSENTE**; slug `pocao-de-cura` (pk 717) **presente**; pk 718 ausente.

## Como aplicar na PRODUÇÃO (passo a passo)

1. **Baixe um backup fresco da produção AGORA** pelo admin (`download_backup_view`). Guarde-o:
   é o rollback real do momento. O rollback base desta rodada é
   `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
2. No **console do admin**, use a ação **"Merge de conteudo (dev -> producao)"**
   (`action=merge_conteudo`), **NÃO** a **"Restauração de backup"**. Faça upload de
   `ref/backups/restore_consolidado_20260718_054605.json`.

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
   `final_counts`/`por_tabela` no `.report.json`). Em especial, `home.tbitemmagico` deve ficar
   em **953**.
5. **(Opcional, para a deleção do 718 valer em prod):** o merge por slug **não remove** slugs
   ausentes. Se `pocao-de-cura-2` ainda existir na prod, remova-o via tombstone em
   `home/content_deletions.json` (PASSO 2.5) ou manualmente pelo admin. Este arquivo apenas
   deixa de contê-lo.

## Plano de rollback

- Se algo sair errado, use a ação **"Restauração de backup"** do console e faça upload do backup
  de produção — de preferência o que você baixou no passo 1; na falta dele,
  `ref/Characterbuilder testes/backup_completo_20260718_015031.json`. Ela faz
  `deserialize().save()` (upsert por PK) e realinha sequences, revertendo o catálogo ao estado do
  backup. Como a memória e o mapa **não foram tocados** por este restore, o rollback afeta só o
  catálogo.

## Aguardando decisão do PO

1. **`TbClassehabilidade` id=967 "Conhecimento Primitivo"** — a mudança `classlvl=10: 2→1` **não**
   estava no escopo enunciado da rodada. Confirmar se deve ir para produção (está incluída por
   dev-vence). Se não, reverter no dev e regerar.
2. **Deleção do item 718 em produção** — decidir se entra por tombstone
   (`home/content_deletions.json`) ou manual; o merge por slug sozinho não o remove.
3. **Mapa / mundo / organizações:** confirmar **PROD VENCE** e **retirar `TbRegiao, TbTerritorio,
   TbMapMarker, TbMapDesenho` da lista `SUBSTITUI` em `home/deploy_sync.py`**. Hoje eles só ficam
   a salvo porque estão AUSENTES deste fixture. **Este arquivo não corrige o `deploy_sync.py` — é
   tarefa à parte.**
4. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Ficou fora.
5. **`TbConquista` vazia no dev (0)** apesar da migração `0052_seed_conquistas`. Se o catálogo de
   conquistas deve existir em prod, **popular o dev e regerar** antes de aplicar (senão vai como 0).
