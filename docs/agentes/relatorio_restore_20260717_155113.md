# Restore de conteúdo prod (dev-vence) — 2026-07-17 15:51:13

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260717_155113.json` (5021 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260717_155113.report.json`
- **SHA-256 do arquivo:** `ad06c86a906dde9ff610104f1a3ba58c1e3c5558961d16f5b87d88ece0713178`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise / prod de referência:** `ref/backups/backup_completo_20260714_214023.json`.
- **Rollback:** `ref/backups/backup_completo_20260714_214023.json`.
- **Substitui:** `restore_consolidado_20260715_013659.json` (mesmo conjunto de 21 modelos, mesmas contagens de linha; só mudaram VALORES de campo).

## O que mudou nesta versão (vs 20260715_013659)

O catálogo do dev evoluiu; a regeneração captura essas mudanças. **Nenhuma linha
nova ou removida** — o diff de contagem vs o report anterior é **zero em todos os
modelos** (`diff_linhas_vs_20260715_013659 = NENHUM`). As mudanças são de conteúdo
de campo em `TbClasse`:

1. **Dados de ficha preenchidos/corrigidos nas 13 classes** de `TbClasse`
   (perícias, armas, ferramentas, armaduras, equipamento, etc.).
2. **`tags_json` ajustadas em 3 classes:** Artífice, Guerreiro e Místico.
3. **`Bardo.equipamento` traduzido para PT-BR.**

Como `TbClasse` é **UPSERT por slug** (preserva o PK da produção), o merge só
atualiza os campos dessas 13 linhas — nenhum ID que os personagens referenciam muda.

## O que este arquivo faz

Empurra o **catálogo de conteúdo** do dev para a produção (dev vence), do jeito
exato da classificação em `home/deploy_sync.py`:

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento,
  TbItemMagico, TbCosmetico`. Casa por `slug`, atualiza os campos, mantém o ID que
  os dados de usuário referenciam. Insere os que não existem. (`TbConquista` está na
  lista mas tem 0 linhas no dev → ausente do fixture.)
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade,
  TbRecursoclasse, TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra,
  TbRecompensaMestre, TbItemMundano, TbBestiario`. (`TbArmadilha` está na lista mas
  tem 0 linhas → ausente do fixture → tabela preservada na prod.)

**O que NÃO está no arquivo (de propósito):** `TbRegiao, TbTerritorio, TbMapMarker,
TbMapDesenho` (estão em `CONTENT_MODELS`/`SUBSTITUI`, mas foram **EXCLUÍDOS**
explicitamente do fixture), além de `TbOrganizacao` e `TbMapLayer` (que nem entram
em nenhuma lista de sync) e toda a **memória** (usuários, personagens, transações,
tabelas do bot). Como o aplicador `sincronizar_conteudo` **pula (e preserva) qualquer
modelo ausente no fixture**, o mapa/mundo e as 81 organizações da staff na produção
ficam **intactos**. A memória nunca é tocada.

> ⚠️ **Nota de ambiente:** o dev **agora espelha o mapa da prod** (`TbRegiao=74,
> TbTerritorio=35, TbMapMarker=74, TbMapDesenho=1`). Isso NÃO muda nada: esses 4
> modelos continuam **fora do fixture** por política prod-vence, e a preservação na
> prod é por **ausência** no arquivo, independente da contagem.

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
| TbItemMagico | upsert_slug | 954 | 954 |
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

Total no arquivo: **5021 registros / 21 modelos** — idêntico em conjunto e contagem
ao `restore_consolidado_20260715_013659`.

## Validação já executada

Apliquei o arquivo via `sincronizar_conteudo` numa **transação revertida (rollback)**
sobre o próprio `db.sqlite3` do dev — nenhuma linha foi persistida (confirmado:
contagem pré == contagem pós):

- **Memória intacta:** 21 tabelas de usuário/missão com a mesma contagem (`mem_ok=True`).
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` entram em
  `pass2_skipped` = "modelo ausente no fixture; tabela preservada" (junto de
  `TbArmadilha`).
- Todos os SUBSTITUI reinseriram a contagem exata do dev; todos os UPSERT casaram por slug.

Spot-checks no fixture (prova de que reflete o dev atual):

- `TbClasse[artifice].armas` = **"Armas Simples e Armas de Fogo"**.
- `TbClasse[guerreiro].pericias` contém **"Persuasão"**.
- `TbClasse[bardo].equipamento` em **PT-BR** ("Escolha A ou B: Armadura de Couro, Besta Leve…").

## Como aplicar na PRODUÇÃO (passo a passo)

1. **Baixe um backup fresco da produção AGORA** pelo admin
   (`/admin/.../download-backup/` → `download_backup_view`). Guarde-o: é o rollback
   real do momento (o `backup_completo_20260714_214023.json` é o rollback base).
2. No **console do admin**, use a ação
   **"Merge de conteudo (dev -> producao)"** (`action=merge_conteudo`), **NÃO** a
   **"Restauração de backup"**. Faça upload de
   `ref/backups/restore_consolidado_20260717_155113.json`.

   > ⚠️ **AVISO — use EXCLUSIVAMENTE o painel "Merge de conteudo (dev -> producao)"
   > para este arquivo.** O painel "Restaurar backup" (upsert por PK) **FALHA** com
   > este fixture — colisão de slug único (`spells_Slug_key`) — porque os PKs do dev
   > e da produção estão desalinhados. Foi o erro observado em produção em 16/07/2026
   > (subiram o arquivo no painel errado). O guard em `home/admin.py` recusa esse
   > upload automaticamente, mas a ação correta continua sendo o merge por slug.
   - Esse fluxo chama `home.deploy_sync.sincronizar_conteudo`: UPSERT por slug
     (preserva PK), SUBSTITUI (delete+reinsert), pula os modelos ausentes (mapa/mundo)
     e roda `sqlsequencereset` no fim (PASSO 3, realinha as sequences do Postgres).
3. **Leia o relatório na tela.** Ele deve dizer, no fim,
   "MEMÓRIA INTACTA: 21 tabelas…" e listar `TbRegiao/TbTerritorio/TbMapMarker/
   TbMapDesenho/TbArmadilha` em "Tabelas preservadas por ausência no fixture".
   Se disser "ATENÇÃO: memória mudou!", **pare** e faça rollback.
4. **Confira as contagens** contra a coluna "Prod depois (esperado)" da tabela acima
   (e contra `final_counts`/`por_tabela` no `.report.json`).

## Plano de rollback

- Se algo sair errado, use a ação **"Restauração de backup"** do console e faça
  upload do backup de produção — de preferência o que você baixou no passo 1;
  na falta dele, `ref/backups/backup_completo_20260714_214023.json`. Ela faz
  `deserialize().save()` (upsert por PK) e realinha sequences, revertendo o catálogo
  ao estado do backup. Como a memória e o mapa **não foram tocados** por este restore,
  o rollback afeta só o catálogo.

## Aguardando decisão do PO

1. **Mapa / mundo / organizações:** confirmar **PROD VENCE** e **retirar `TbRegiao,
   TbTerritorio, TbMapMarker, TbMapDesenho` da lista `SUBSTITUI` em
   `home/deploy_sync.py`**. Hoje eles só ficam a salvo porque estão AUSENTES deste
   fixture; um `sync_conteudo`/`dump_conteudo` padrão (que inclui esses modelos) os
   apagaria. **Este arquivo não corrige o `deploy_sync.py` — é tarefa à parte.**
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Ficou fora.
3. **`TbConquista` vazia no dev (0)** apesar da migração `0052_seed_conquistas`. Se o
   catálogo de conquistas deve existir em prod, **popular o dev e regerar** antes de
   aplicar (senão vai como 0).
