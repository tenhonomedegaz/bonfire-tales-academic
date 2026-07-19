# Restore de conteúdo prod (dev-vence) — 2026-07-19 20:05:33 — R3 FINAL

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260719_200533.json` (5021 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260719_200533.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF):** `635677d7de429955d1a60e471f3fcf1bfe9ce92a72d041647a6488d2449f471b`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise / prod de referência:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
- **Rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
- **Substitui:** `restore_consolidado_20260719_034304.json` (mesmo conjunto de 21 modelos e **exatamente a mesma contagem de linhas** — 5021 registros; só mudam **valores** de tag/recurso de 63 linhas em 6 tabelas, pela remodelagem **R3 final**).

## O que mudou nesta versão (vs 20260719_034304)

Esta versão captura a **rodada R3 (final)** da remodelagem, registrada em
`scratchpad/remodelagem/log_aplicacao_r3.jsonl`. O log tem **185 registros** (fora as 2
linhas de comentário `#`): **99** com `tabela`+`pk` (tocam **93 linhas distintas**) e **86**
de reprocessamento dos holds da R2 (documentação, sem mutação nova).

**Nenhuma linha foi inserida ou removida** (`inserted=0`, `removed=0`): as **21 contagens de
linha ficam idênticas** ao 034304 e `final_records` continua **5021**. Mudou apenas o **valor**
(bytes) de **63 linhas** distribuídas em **6 tabelas**. Diff por PK contra o fixture anterior:

| Tabela | Campo alterado | Linhas com bytes alterados |
|---|---|---:|
| TbAntecedente | `tags_json` | 2 |
| TbOpcaojogo | `tags_json` | 5 |
| TbTalento | `tags_json` | 7 |
| TbClassehabilidade | `tags_json` | 38 |
| TbRecursoclasse | `valores_json`×2 + `reset`×1 | 3 |
| TbTracoracial | `tags_json` | 8 |
| **Total** | | **63** |

Natureza das 63 alterações (todas UPDATE de linha existente, cruzadas 1-a-1 com o log R3):

1. **Estilos de luta canonizados** (`TbOpcaojogo`): Arquearia (`ranged.weapon.attack:+2` →
   `ranged.atk:+2`), Defesa (`ca:+1` → `armor.ca:+1`), Combate Desarmado (forma canônica
   `unarmed_strike.dmg:=…`), e `cr<=1` → `max_cr:1` (OP#161). 4 `aplicado` + 1 `remove_tag`.
2. **Remaps de magia** (`TbClassehabilidade`, 8 `remapeia_magia`): `mao_magica` → `mao_arcana`
   (CH#1268/1269/1281/1307), `marca_da_punicao` → `golpe_brilhante` (CH#906),
   `potencializar_pericia` → `aprimoramento_de_pericia` (CH#899), `deslocamento_temporal` →
   `derivacao_temporal` (CH#909).
3. **Narrativo destaggeado / verbos inertes limpos**: 11 `remove_tag` + 7 `remove_token` +
   3 `convert_verbo` (`immune` → `immune_effect`) — categorias `narrativa_pura` (18) e
   `combate_inerte` (11) do log.
4. **Recursos por fórmula** (`TbRecursoclasse`, 3 `recurso_fix`): **Fúrias** (pk3758)
   `valores_json {1:2,3:3,6:4,12:5,17:6}` → **`{1:pb}`** (descrição: usos = Bônus de
   Proficiência); **Truques do Trapaceiro Arcano** (pk1) → `{3:3,10:4}` (off-by-one corrigido);
   **Canalizar Divindade** (pk3760) `reset short-or-long` → `long-rest`. Contagem intacta (135).

**Expertise "revividas" não alteram o fixture:** os 11 `revivido` (e os `guard`/`mantido`) são
mudança de **motor** (o `character_engine` agora consome `expertise:<pericia>` /
`pick:pericia_expertise` que **já estavam no DB** desde as rodadas anteriores). Por isso a linha
não muda de bytes — a capacidade passa a ter efeito por código, não por retag. Há **24 registros**
com o verbo `expertise:` vivo no fixture.

Prova de integridade: os `sha256_registros` das **15 tabelas restantes** batem **exatamente**
com os do report de 20260719_034304 (incluindo `TbClasse` e `TbCondicao`, que a R2 mexeu mas a
R3 não). Só estas **6 tabelas** mudaram de sha.

## O que este arquivo faz

Empurra o **catálogo de conteúdo** do dev para a produção (dev vence), do jeito exato da
classificação em `home/deploy_sync.py`:

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento, TbItemMagico,
  TbCosmetico`. Casa por `slug`, atualiza os campos, mantém o ID que os dados de usuário
  referenciam. (`TbConquista` está na lista mas tem 0 linhas no dev → ausente do fixture.)
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade,
  TbRecursoclasse, TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra,
  TbRecompensaMestre, TbItemMundano, TbBestiario`. (`TbArmadilha` está na lista mas tem 0
  linhas → ausente → tabela preservada na prod.)

**O que NÃO está no arquivo (de propósito):** `TbRegiao, TbTerritorio, TbMapMarker,
TbMapDesenho` (estão em `CONTENT_MODELS`/`SUBSTITUI`, mas foram **EXCLUÍDOS** do fixture),
além de `TbOrganizacao` e `TbMapLayer` (que nem entram em nenhuma lista de sync) e toda a
**memória** (usuários, personagens, transações, tabelas do bot). Como o aplicador
`sincronizar_conteudo` **pula (e preserva) qualquer modelo ausente no fixture**, o mapa/mundo
e as 81 organizações da staff na produção ficam **intactos**. A memória nunca é tocada.

## Números por tabela (dev-vence)

| Tabela | Ação | No arquivo | Prod depois (esperado) | Δ linhas vs 034304 |
|---|---|---:|---:|---:|
| TbRaca | upsert_slug | 4 | 4 | 0 |
| TbLinhagem | upsert_slug | 16 | 16 | 0 |
| TbEssencia | upsert_slug | 4 | 4 | 0 |
| TbAntecedente | upsert_slug | 30 | 30 | 0 (2 retag) |
| TbClasse | upsert_slug | 13 | 13 | 0 |
| TbSubclasse | upsert_slug | 111 | 111 | 0 |
| TbOpcaojogo | upsert_slug | 259 | 259 | 0 (5 retag) |
| TbMagia | upsert_slug | 580 | 580 | 0 |
| TbTalento | upsert_slug | 139 | 139 | 0 (7 retag) |
| TbItemMagico | upsert_slug | 953 | 953 | 0 |
| TbCosmetico | upsert_slug | 24 | 24 | 0 |
| TbClassehabilidade | substitui | 884 | 884 | 0 (38 retag) |
| TbRecursoclasse | substitui | 135 | 135 | 0 (3 recurso_fix) |
| TbAcessoopcao | substitui | 97 | 97 | 0 |
| TbTracoracial | substitui | 352 | 352 | 0 (8 retag) |
| TbCondicao | substitui | 28 | 28 | 0 |
| TbIdioma | substitui | 22 | 22 | 0 |
| TbRegra | substitui | 139 | 139 | 0 |
| TbRecompensaMestre | substitui | 9 | 9 | 0 |
| TbItemMundano | substitui | 302 | 302 | 0 |
| TbBestiario | substitui | 920 | 920 | 0 |
| **TbRegiao** | **skip/preserva** | — | **74** | fora |
| **TbTerritorio** | **skip/preserva** | — | **35** | fora |
| **TbMapMarker** | **skip/preserva** | — | **74** | fora |
| **TbMapDesenho** | **skip/preserva** | — | **1** | fora |
| **TbOrganizacao** | **fora do sync** | — | **81** | fora |
| **TbMapLayer** | **PO decide** | — | **4** | fora |
| TbConquista / TbArmadilha | 0 linhas → ausente | — | preservado | — |

Total no arquivo: **5021 registros / 21 modelos** — **mesmo conjunto e mesma contagem** do
`restore_consolidado_20260719_034304`. **Cada diff de contagem = 0** e está explicado acima:
a R3 é 100% UPDATE de valor (63 linhas), sem `INSERT`/`DELETE`.

## Validação já executada

Apliquei o arquivo via `sincronizar_conteudo` numa **transação revertida (rollback)** sobre o
próprio `db.sqlite3` do dev — nenhuma linha foi persistida (confirmado: contagem pré == pós):

- **Memória intacta:** 21 tabelas de usuário/missão com a mesma contagem (`mem_ok=True`).
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` entram em
  `pass2_skipped` (junto de `TbArmadilha`). Contagens antes/depois idênticas (74/35/74/1).
- Todos os SUBSTITUI reinseriram a contagem exata do dev; todos os UPSERT casaram por slug
  (prod = subset por slug).
- Os `sha256_registros` das **15 tabelas não tocadas pela R3** batem exatamente com os do
  report de 20260719_034304.

Spot-checks no fixture (bytes em disco):

- `TbOpcaojogo[43]` (Arquearia) — `tag_depois` do log presente: `["always_active{ ranged.atk:+2 }"]`.
- `TbClassehabilidade[901]` (Armas Integradas) — `["natural.dmg:=1d10", "natural.attr:=des"]`.
- `TbClassehabilidade[663]` (Feitiçaria Inata) — `define{ feiticaria_inata: uses:2, reset:long_rest }` presente.
- `TbRecursoclasse[3758]` (Fúrias) — `valores_json == {"1": "pb"}` (recurso por fórmula).
- `TbClassehabilidade[773]` (Conhecimentos Arcanos) — `expertise:arcanismo` vivo (24 registros com `expertise:` no fixture).

## Como aplicar na PRODUÇÃO (passo a passo)

1. **Baixe um backup fresco da produção AGORA** pelo admin (`download_backup_view`). Guarde-o:
   é o rollback real do momento. O rollback base desta rodada é
   `ref/Characterbuilder testes/backup_completo_20260718_015031.json`.
2. No **console do admin**, use a ação **"Merge de conteudo (dev -> producao)"**
   (`action=merge_conteudo`), **NÃO** a **"Restauração de backup"**. Faça upload de
   `ref/backups/restore_consolidado_20260719_200533.json`.

   > ⚠️ **AVISO — use EXCLUSIVAMENTE o painel "Merge de conteudo (dev -> producao)" para este
   > arquivo.** O painel "Restaurar backup" (upsert por PK) **FALHA** com este fixture — colisão
   > de slug único (`spells_Slug_key`) — porque os PKs do dev e da produção estão desalinhados.
   > O guard em `home/admin.py` recusa esse upload automaticamente; a ação correta é o merge por slug.
   - Esse fluxo chama `home.deploy_sync.sincronizar_conteudo`: UPSERT por slug (preserva PK),
     SUBSTITUI (delete+reinsert), pula os modelos ausentes (mapa/mundo) e roda `sqlsequencereset`
     no fim (PASSO 3, realinha as sequences do Postgres).
3. **Leia o relatório na tela.** Ele deve dizer, no fim, "MEMÓRIA INTACTA: 21 tabelas…" e listar
   `TbRegiao/TbTerritorio/TbMapMarker/TbArmadilha/TbMapDesenho` em "Tabelas preservadas por
   ausência no fixture". Se disser "ATENÇÃO: memória mudou!", **pare** e faça rollback.
4. **Confira as contagens** contra a coluna "Prod depois (esperado)" da tabela acima (e contra
   `final_counts`/`por_tabela` no `.report.json`). **Nesta rodada todas as 21 contagens são iguais
   às do 034304** (R3 = só valores); em especial `home.tbcondicao` fica em **28** e
   `home.tbitemmagico` em **953**.

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
