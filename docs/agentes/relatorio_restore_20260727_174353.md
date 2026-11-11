# Restore final — holds de equipabilidade resolvidos

- **Gerado em:** 2026-07-27 17:43:53 (dev reconciliado, branch `dev`)
- **Arquivo:** `ref/backups/restore_consolidado_20260727_174353.json`
- **SHA-256:** `fde03084d41467f4ca00b25d8f4ab4bc6fc4ab6ad8c408e093fa9942a9fe1e7a`
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260727_174353.report.json`
- **Baseline de análise:** `ref/backups/restore_consolidado_20260727_000359.json`
- **Rollback:** `ref/backup_completo_20260722_230533.json`
- **Aplicador:** admin console → ação `merge_conteudo` (`home.deploy_sync.sincronizar_conteudo`)
- **Princípio:** CONTEÚDO dev-vence (upsert por slug); MAPA/MUNDO prod-vence; MEMÓRIA preservada por ausência.

> Este restore **supersede** `relatorio_restore_20260727_000359.md` (removido nesta rodada). Os artefatos `.json` / `.report.json` ficam **apenas em disco** (pasta `ref/`, gitignored). Este `.md` é o único item versionado desta etapa.

## Validação executada

| Gate | Resultado |
| --- | --- |
| `json.load` + `deserialize` do fixture | 5061 / 5061 registros (100%) |
| `sincronizar_conteudo` em `transaction.atomic()` + `set_rollback(True)` | `mem_ok = true` (memória intacta) |
| Modelos de memória presentes no fixture | nenhum (`memory_models_in_fixture: []`) |
| Pass-2 pulado (preserva prod) | `TbRegiao, TbTerritorio, TbMapMarker, TbArmadilha, TbMapDesenho` |
| Line endings / BOM | CRLF / BOM=true |
| `manage.py validate_tags` | **ERROR=0**, WARN=34, INFO=0 (warns pré-existentes de `innate-cast-uses`) |
| `manage.py test home.test_equipabilidade_itens home.test_conceder_item home.test_loja_ficha` | **29 testes, OK** (176s) |

**Contagem total:** 5061 registros (baseline 5063 → **−2 líquidos**), explicados na tabela de diferenças.

## Os 20 holds de equipabilidade — resolvidos

A varredura de equipabilidade deixou **20 itens em hold** (todos parados em `empunhado`, confiança baixa), listados em `scratch/equipaveis_aplicacao_log.json` → chave `holds`. Decisão do PO: **aplicar todos**, com um override.

> **Regra do PO para formas exóticas:** quando o item não tem slot anatômico correspondente no catálogo, o fallback é **`acessorio`** — acessório *dá o efeito sem consumir slot*, o que é mais simples do que criar um slot novo (montaria, implante, simbionte ingerido).

Resultado: **14 alterados, 6 mantidos**. O log recebeu a chave `holds_aplicados` com `{slug, de, para, decisao}` por item.

### Alterados (14)

| # | Slug | De | Para | Decisão |
| ---: | --- | --- | --- | --- |
| 1 | `membro-protetico` | `empunhado` | `acessorio` | proposta |
| 2 | `membro-protetico-2` | `empunhado` | `acessorio` | proposta |
| 3 | `membro-protetico-3` | `empunhado` | `acessorio` | proposta |
| 4 | `membro-protetico-4` | `empunhado` | `acessorio` | proposta |
| 5 | `laco-dimensional` | `empunhado` | `acessorio` | proposta |
| 6 | `relogio-de-viagem` | `empunhado` | `acessorio` | proposta |
| 7 | `rotor-de-retorno` | `empunhado` | `acessorio` | proposta |
| 8 | `paciencia-de-fragmentos` | `empunhado` | `acessorio` | proposta |
| 9 | `far-gear` | `empunhado` | `item_menor` | proposta |
| 10 | `fragmento-da-runa-de-ise` | `empunhado` | `item_menor` | proposta |
| 11 | `cachecol-de-platina` | `empunhado` | `acessorio` | **po-override** (proposta era `objeto`) |
| 12 | `lodo-de-kyrzin` | `empunhado` | `acessorio` | **po-override** (proposta era `pele`) |
| 13 | `sela-do-cavaleiro` | `empunhado` | `acessorio` | **po-override** (proposta era `acessorio`/montaria) |
| 14 | `ventilacao-dos-pulmoes` | `empunhado` | `acessorio` | **po-override** (proposta era `torso`) |

Os 4 **casos únicos** (11-14) eram justamente os que não têm slot anatômico honesto: escamas destacáveis, simbionte ingerido, equipamento de montaria e implante interno. Todos caem em `acessorio` pela regra acima.

### Mantidos em `empunhado` (6, no-op)

`foco-ascendente-tocado-pelo-dragao`, `foco-desperto-tocado-pelo-dragao`, `foco-inspirador-tocado-por-dragoes`, `foco-tocado-por-dragao-adormecido`, `imbued-wood`, `icone-de-ravenloft`.

São focos de forma variável (haste/bastão/varinha) e o Ícone de Ravenloft, que mistura aura por proximidade com propriedades que exigem segurar. `empunhado` continua sendo o slot funcional conservador — registrados como no-op, sem UPDATE.

## Diferenças vs baseline (cada uma explicada)

> **Atenção — o baseline `20260727_000359` está defasado.** Ele foi gerado **antes** do lote de equipabilidade de 266 itens ser aplicado ao banco. Portanto o diff abaixo **não** mostra apenas os 14 slots desta rodada: mostra `266 (lote anterior) + 14 (holds) = 280` alterações de `slot`, mais o churn de outras frentes. A atribuição foi verificada item a item contra `scratch/equipaveis_aplicacao_log.json` — ver "Atribuição" abaixo.

| Modelo | alterados | +inseridos | -removidos | Causa |
| --- | ---: | ---: | ---: | --- |
| `tbitemmagico` | 285 (`slot` 280, `tags_json` 2, `nome` 1, `slug` 1, `descricao_markdown` 1) | 0 | 2 | **Equipabilidade**: 266 do lote anterior + **14 holds desta rodada**. `nome`/`slug`/`descricao` = commit `9d9fcd1` (`babador-de-acougueiro` → `avental-de-acougueiro`, pk 164). As 2 remoções = poção duplicada (pk 718) e avental fantasma (pk 955), do mesmo commit. |
| `tbmagia` | 5 registros (todos os campos) | 0 | 0 | **Churn de PK** com slug estável (re-serialização/remap). Merge é por slug → inócuo. |
| `tbclassehabilidade` | 1 (`tags_json`) | 79 | 78 | **Churn de PK** + retag residual. Net **+1**. |
| `tbrecursoclasse` | 0 | 14 | 15 | **Churn de PK** dos recursos. Net **−1**. |
| `tbacessoopcao` | 0 | 22 | 22 | **Churn de PK** puro (pk 186-207 → 120-141). Net 0. |
| `tbcosmetico` | 0 | 6 | 6 | **Churn de PK** com slug estável; inócuo ao merge por slug. Net 0. |
| `tbopcaojogo` | 4 (`tags_json`) | 0 | 0 | Retag residual de opções. |
| `tbclasse` | 1 (`tags_json`) | 0 | 0 | Retag residual. |
| `tbtracoracial` | 1 (`tags_json`) | 0 | 0 | Retag residual. |

**Net de linhas:** `−2` (itens mágicos) `+1` (habilidades) `−1` (recursos) = **−2** → 5063 → 5061. Nenhum modelo de memória tocado.

### Atribuição dos 280 slots (verificada)

Reconstrução do conjunto `(pk, de, para)` observado no fixture contra o log:

- **280** diffs de `slot` observados = **266** (`alteracoes` do lote anterior) ∪ **14** (`holds_aplicados` desta rodada) — casam **279/280**.
- Os **14 desta rodada** foram confirmados **um a um** no fixture novo (slot final == slot decidido). Zero falha.
- **1 divergência pré-existente, fora deste escopo:** pk **105** (`apito-da-aguia`) foi registrado no log do lote anterior como `empunhado → item_menor`, mas o banco está em `objeto`. Não é um dos 20 holds e não foi tocado aqui — fica registrado para a frente de equipabilidade conferir.

## Checklist de aplicação em produção (runbook)

1. **Migrar ANTES do merge (gate duro).** Aplicar `python manage.py migrate home` com as migrações **0066-0084** já na prod (`force_update`). A **0072** é obrigatória antes do merge: cria a coluna `TagsJSON` em `TbEssencia` — sem ela o loaddata dos registros de essência falha. As demais (data migrations) são idempotentes com o conteúdo do restore (que já traz os valores pós-migração).
2. **Backup completo da produção** imediatamente antes do merge.
3. **Merge de conteúdo:** admin console → ação `merge_conteudo` apontando para `restore_consolidado_20260727_174353.json` (`home.deploy_sync.sincronizar_conteudo`). Upsert por slug; mundo/mapa e memória preservados.
4. **Rollback:** em caso de falha, restaurar `ref/backup_completo_20260722_230533.json` (`loaddata`).
5. **Smoke pós-merge:**
   - **Equipabilidade dos holds:** `membro-protetico` e `sela-do-cavaleiro` aparecem como `acessorio` na ficha; `far-gear` como `item_menor`; os 4 focos tocados por dragão seguem `empunhado`.
   - **Acessório não consome slot:** equipar um dos 14 não bloqueia mão/torso.
   - **Bardo reworkado:** habilidades, 22 opções (`acorde-lendario` etc.), recurso `Acordes` e taglines dos colégios presentes.
   - **Paladino prepara:** conjuração de Paladino N5 lista magias preparadas.
   - **`validate_tags` não crasha:** `python manage.py validate_tags` roda até o fim (ERROR=0 nesta rodada).

## Rastreabilidade

- Fonte da decisão: `scratch/equipaveis_aplicacao_log.json` → chaves `holds` (entrada) e `holds_aplicados` (saída desta rodada).
- Commits que produziram este estado (branch `dev`):
  - `feat(tag-engine): motor de tags v2 ... (migracoes 0066-0084)`
  - `feat(bardo): rework integral ...`
  - `feat(pathbuilder): laboratorio de builds A/B ...`
  - `fix(fixture): reconcilia conteudo.json ao banco ...` (`9d9fcd1`)
  - `docs(deploy): restore com holds de equipabilidade resolvidos ...` (este)
