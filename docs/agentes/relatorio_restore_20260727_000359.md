# Restore final — pós tag-engine v2 + Bardo rework

- **Gerado em:** 2026-07-27 00:03:59 (dev reconciliado, branch `dev`)
- **Arquivo:** `ref/backups/restore_consolidado_20260727_000359.json`
- **SHA-256:** `0aee43525e545fa9d90b90a266d511ce978058efd1765bb555f7153097c3fbb9`
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260727_000359.report.json`
- **Baseline de análise:** `ref/backups/restore_consolidado_20260723_225159.json`
- **Rollback:** `ref/backup_completo_20260722_230533.json`
- **Aplicador:** admin console → ação `merge_conteudo` (`home.deploy_sync.sincronizar_conteudo`)
- **Princípio:** CONTEÚDO dev-vence (upsert por slug); MAPA/MUNDO prod-vence; MEMÓRIA preservada por ausência.

> Os artefatos `.json` / `.report.json` ficam **apenas em disco** (pasta `ref/`, gitignored). Este `.md` é o único item versionado desta etapa.

## Validação executada

| Gate | Resultado |
| --- | --- |
| `json.load` + `deserialize` do fixture | 5063 / 5063 registros (100%) |
| `sincronizar_conteudo` em `transaction.atomic()` + `set_rollback(True)` | `mem_ok = true` (memória intacta) |
| Modelos de memória presentes no fixture | nenhum (`memory_models_in_fixture: []`) |
| Pass-2 pulado (preserva prod) | `TbRegiao, TbTerritorio, TbMapMarker, TbArmadilha, TbMapDesenho` |
| Line endings / BOM | CRLF / BOM=true |
| `manage.py check` | 0 issues |

**Contagem total:** 5063 registros (baseline 5012 → **+51 líquidos**). Cada diferença abaixo é explicada por um dos três eixos da rodada: **retag/saneamento** (motor de tags v2 + migrações 0066-0084), **Bardo** (rework integral) e **Paladino** (conjurador que prepara + limpeza de órfãs).

## Diferenças vs baseline (cada uma explicada)

| Modelo | alterados | +inseridos | -removidos | Causa |
| --- | ---: | ---: | ---: | --- |
| `tbtracoracial` | 129 (`tags_json`) | 0 | 0 | **Retag** dos traços raciais (migrações 0067/0071/0073-0084: darkvision split, sentidos, negação, olhos umbrais, movimento). |
| `tbitemmagico` | 400 (`slot` 266, `tags_json` 174) | 2 | 0 | **Retag** itens mágicos (limpeza de metadados + normalização de sintaxe/slot — migrações 0068/0070). +2 = `babador-de-acougueiro` (novo) e `pocao-de-cura-2` (dedup de poção). |
| `tbclassehabilidade` | 181 (`tags_json`) | 78 | 74 | **Retag** (181) + **Bardo** (reimport apaga antigas / cria novas com PK fresco) + **Paladino** (órfãs deletadas + re-tag). Net +4. |
| `tbopcaojogo` | 85 (`tags_json`) | 22 | 0 | **Retag** (85) + **Bardo** (22 novas opções: `acorde-lendario`, `adagio`, `cancao-de-descanso`, `melodia-inspiradora`, ...). |
| `tbtalento` | 61 (`tags_json`) | 0 | 0 | **Retag** dos talentos. |
| `tbantecedente` | 29 (`tags_json`) | 0 | 0 | **Retag** dos antecedentes (padrão uniforme). |
| `tbacessoopcao` | 0 | 22 | 0 | **Bardo** — linhas de acesso (`pk 186-207`) das 22 opções novas do Bardo. |
| `tbrecursoclasse` | 13 (`id_classe` 12, `nivel` 13, `valor` 13, `valores_json` 2) | 1 (`acordes`) | 0 | **Bardo** — recurso `Acordes` novo + reestruturação de recursos (Inspiração etc.); `valores_json` cobre o ajuste de conjuração (Bardo/Paladino). |
| `tbbestiario` | 11 (`tags_json`) | 0 | 0 | **Retag** de statblocks. |
| `tbsubclasse` | 8 (`tagline`) | 0 | 0 | **Bardo** — taglines dos colégios/subclasses reworkadas. |
| `tbmagia` | 5 (sem campo mecânico) | 0 | 0 | **Churn de PK** com slug estável (re-serialização/remap de magias); merge é por slug → inócuo. |
| `tbcosmetico` | 6 (sem campo mecânico) | 0 | 0 | **Churn de PK** com slug estável; inócuo ao merge por slug. |
| `tbessencia` | 4 (`tags_json`) | 0 | 0 | **Migração 0072** — política de pick de maldição movida para a essência (`suppress:pick{talento_racial, source:raca}`). Campo `tags_json` novo em `TbEssencia`. |
| `tbclasse` | 2 (`tags_json`; 1 classe com `equipamento`/`ferramentas`/`multiclass_*`/`pericias`/`pv_por_nivel`) | 0 | 0 | **Bardo** (redefine proficiências/equipamento/PV do Bardo) + **Paladino/retag** (`tags_json` da 2ª classe: tag de conjurador que prepara). |

Nenhum registro removido fora de `tbclassehabilidade` (as 74 remoções são habilidades antigas do Bardo/órfãs do Paladino, substituídas por versões reimportadas/re-tagueadas). Nenhum modelo de memória tocado.

## Checklist de aplicação em produção (runbook)

1. **Migrar ANTES do merge (gate duro).** Aplicar `python manage.py migrate home` com as migrações **0066-0084** já na prod (`force_update`). A **0072** é obrigatória antes do merge: cria a coluna `TagsJSON` em `TbEssencia` — sem ela o loaddata dos registros de essência falha. As demais (data migrations) são idempotentes com o conteúdo do restore (que já traz os valores pós-migração).
2. **Backup completo da produção** imediatamente antes do merge.
3. **Merge de conteúdo:** admin console → ação `merge_conteudo` apontando para `restore_consolidado_20260727_000359.json` (`home.deploy_sync.sincronizar_conteudo`). Upsert por slug; mundo/mapa e memória preservados.
4. **Rollback:** em caso de falha, restaurar `ref/backup_completo_20260722_230533.json` (`loaddata`).
5. **Smoke pós-merge:**
   - **Bardo reworkado:** habilidades, 22 opções (`acorde-lendario` etc.), recurso `Acordes` e taglines dos colégios presentes.
   - **Paladino prepara:** conjuração de Paladino N5 lista magias preparadas.
   - **Maestria troca:** troca de maestria de arma funciona na ficha.
   - **`validate_tags` não crasha:** `python manage.py validate_tags` roda até o fim (ERROR conforme baseline da rodada).

## Rastreabilidade

- Commits que produziram este estado (branch `dev`):
  - `feat(tag-engine): motor de tags v2 ... (migracoes 0066-0084)`
  - `feat(bardo): rework integral ...`
  - `feat(pathbuilder): laboratorio de builds A/B ...`
  - `docs(agentes): relatorios do conjunto tag-engine/bardo/pathbuilder`
