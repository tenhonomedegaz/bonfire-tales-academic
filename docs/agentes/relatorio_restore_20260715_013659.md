# Restore de conteúdo prod (dev-vence) — 2026-07-15 01:36:59

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260715_013659.json` (5021 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260715_013659.report.json`
- **SHA-256 do arquivo:** `fc462d26154e09e3a1117615202b0db5cfaf734b98189b13a474dee7cee8cf9f`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise:** `ref/backups/backup_completo_20260714_214023.json` + `scratchpad/restore_prod/analise_prod_dev.md`
- **Rollback:** o próprio `backup_completo_20260714_214023.json`.

## O que este arquivo faz

Empurra o **catálogo de conteúdo** do dev para a produção (dev vence), do jeito
exato da classificação em `home/deploy_sync.py`:

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento,
  TbItemMagico, TbCosmetico, TbConquista`. Casa por `slug`, atualiza os campos,
  mantém o ID que os dados de usuário referenciam. Insere os que não existem.
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade,
  TbRecursoclasse, TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra,
  TbRecompensaMestre, TbItemMundano, TbBestiario, TbArmadilha`.

**O que NÃO está no arquivo (de propósito):** `TbRegiao, TbTerritorio,
TbMapMarker, TbMapDesenho, TbOrganizacao, TbMapLayer` e toda a **memória**
(usuários, personagens, transações, tabelas do bot). Como o aplicador
`sincronizar_conteudo` **pula (e preserva) qualquer modelo ausente no fixture**,
o mapa/mundo e as 81 organizações da staff na produção ficam **intactos**. A
memória nunca é tocada.

## Números por tabela (dev-vence)

| Tabela | Ação | Prod antes | No arquivo | Prod depois (esperado) |
|---|---|---:|---:|---:|
| TbClasse | upsert_slug | 13 | 13 | 13 |
| TbClassehabilidade | substitui | 867 | 884 | 884 |
| TbOpcaojogo | upsert_slug | 241 | 259 | 259 |
| TbMagia | upsert_slug | 580 | 580 | 580 |
| TbTalento | upsert_slug | 139 | 139 | 139 |
| TbTracoracial | substitui | 352 | 352 | 352 |
| TbItemMagico | upsert_slug | 954 | 954 | 954 |
| TbItemMundano | substitui | 302 | 302 | 302 |
| TbCondicao | substitui | 27 | 27 | 27 |
| TbAntecedente | upsert_slug | 30 | 30 | 30 |
| TbBestiario | substitui | 920 | 920 | 920 |
| TbCosmetico | upsert_slug | 24 | 24 | 24 |
| TbSubclasse | upsert_slug | 110 | 111 | 111 |
| TbRecursoclasse | substitui | 131 | 135 | 135 |
| TbAcessoopcao | substitui | 97 | 97 | 97 |
| TbRaca / TbEssencia / TbLinhagem | upsert_slug | 4 / 4 / 16 | 4 / 4 / 16 | 4 / 4 / 16 |
| TbRegra / TbIdioma / TbRecompensaMestre | substitui/upsert | 139 / 22 / 9 | 139 / 22 / 9 | 139 / 22 / 9 |
| TbConquista | upsert_slug | 0 | 0 | 0 (vazio) |
| TbArmadilha | substitui | 0 | 0 | 0 (vazio → preservado) |
| **TbRegiao** | **skip/preserva** | **74** | — | **74** |
| **TbTerritorio** | **skip/preserva** | **35** | — | **35** |
| **TbMapMarker** | **skip/preserva** | **74** | — | **74** |
| **TbMapDesenho** | **skip/preserva** | **1** | — | **1** |
| **TbOrganizacao** | **fora do sync** | **81** | — | **81** |
| **TbMapLayer** | **PO decide** | **4** | — | **4** |

> Nota UPSERT: a "prod depois" assume prod SUBSET|IGUAL do dev por slug (confirmado
> na análise). Se a prod tiver algum slug que o dev não tem, o UPSERT o **preserva**
> (post-count seria maior). Nenhum caso desses foi encontrado.

## Validação já executada

Apliquei o arquivo via `sincronizar_conteudo` numa **cópia descartável** do db dev
(o `db.sqlite3` real não foi tocado):

- **Memória intacta:** 21 tabelas de usuário/missão com a mesma contagem (`mem_ok=True`).
- **Mapa preservado:** `TbRegiao/TbTerritorio/TbMapMarker/TbMapDesenho` inalterados
  (entram em `pass2_skipped` = "modelo ausente no fixture; tabela preservada").
- Todos os SUBSTITUI reinseriram a contagem exata do dev; todos os UPSERT casaram por slug.

## Como aplicar na PRODUÇÃO (passo a passo)

1. **Baixe um backup fresco da produção AGORA** pelo admin
   (`/admin/.../download-backup/` → `download_backup_view`). Guarde-o: é o rollback
   real do momento (o `backup_completo_20260714_214023.json` é o rollback base).
2. **Confirme os itens "aguardando decisão do PO"** (seção abaixo) — principalmente
   que os 6 traços dracônicos e a `Maestria em Armas` só-em-prod foram reworkados no
   dev (o SUBSTITUI de `TbClassehabilidade` vai apagá-los e reinserir os 884 do dev).
3. No **console do admin** (a mesma tela dos precedentes), use a ação
   **"Merge de conteudo (chave natural)"** (`action=merge_conteudo`), NÃO a
   "Restauracao de backup". Faça upload de
   `ref/backups/restore_consolidado_20260715_013659.json`.
   - Esse fluxo chama `home.deploy_sync.sincronizar_conteudo`: UPSERT por slug
     (preserva PK), SUBSTITUI (delete+reinsert), pula os modelos ausentes (mapa/mundo)
     e roda `sqlsequencereset` no fim (PASSO 3, realinha as sequences do Postgres).
   - **Por que `merge_conteudo` e não `restore_backup`:** a "Restauracao de backup"
     faz upsert cru **por PK** e deixaria os 14 registros de `TbBestiario` e os 6 de
     `TbCosmetico` com PK desalinhado na prod (duplicatas). O `merge_conteudo` resolve
     o desalinhamento (delete+reinsert no Bestiário; match por slug no Cosmético).
4. **Leia o relatório na tela.** Ele deve dizer, no fim,
   "MEMÓRIA INTACTA: 21 tabelas..." e listar `TbRegiao/TbTerritorio/TbMapMarker/
   TbMapDesenho/TbArmadilha` em "Tabelas preservadas por ausência no fixture".
   Se disser "ATENÇÃO: memória mudou!", **pare** e faça rollback.
5. **Confira as contagens** contra a coluna "Prod depois (esperado)" da tabela acima
   (e contra `final_counts`/`por_tabela` no `.report.json`).

## Plano de rollback

- Se algo sair errado, use a ação **"Restauracao de backup"** do console e faça
  upload do backup de produção — de preferência o que você baixou no passo 1;
  na falta dele, `ref/backups/backup_completo_20260714_214023.json`. Ela faz
  `deserialize().save()` (upsert por PK) e realinha sequences, revertendo o catálogo
  ao estado do backup. Como a memória e o mapa **não foram tocados** por este restore,
  o rollback afeta só o catálogo.

## Aguardando decisão do PO (ficou FORA do arquivo)

1. **Mapa / mundo / organizações (maior risco):** confirmar **PROD VENCE** e
   **retirar `TbRegiao, TbTerritorio, TbMapMarker, TbMapDesenho` da lista `SUBSTITUI`
   em `home/deploy_sync.py`** enquanto o dev estiver atrás. Hoje eles só ficam a salvo
   porque estão AUSENTES deste fixture; um `sync_conteudo`/`dump_conteudo` padrão
   (que inclui esses modelos) os apagaria e injetaria lixo de teste. **Este arquivo
   não corrige o `deploy_sync.py` — é uma tarefa à parte.**
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Decidir se a camada 1
   fica pública (prod) ou oculta (dev). Ficou fora.
3. **`TbClassehabilidade` — 6 traços dracônicos (classe 7) + `Maestria em Armas`
   só-em-prod:** confirmar que foram reworkados/renomeados no dev (dev vence) e não
   perdidos por engano. O SUBSTITUI vai removê-los.
4. **`TbConquista` vazia no dev (0)** apesar da migração `0052_seed_conquistas`. Se o
   catálogo de conquistas deve existir em prod, **popular o dev e regerar** antes de
   aplicar (senão vai como 0).
