# Restore da onda leve pós-Ficha v2 — moeda composta, wizard direto e saneamento de conteúdo

- **Gerado em:** 2026-07-28 19:43:51 (dev reconciliado, branch `dev`)
- **Arquivo:** `ref/backups/restore_consolidado_20260728_194351.json`
- **SHA-256:** `be53e511e9e705fe776763bf425c84c99a0e055f683cf3e0c4dcb682988b4e3d`
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260728_194351.report.json`
- **Baseline de análise:** `ref/backups/restore_consolidado_20260727_174353.json`
- **Rollback:** `ref/backup_completo_20260722_230533.json`
- **Aplicador:** admin console → ação `merge_conteudo` (`home.deploy_sync.sincronizar_conteudo`)
- **Princípio:** CONTEÚDO dev-vence (upsert por slug); MAPA/MUNDO prod-vence; MEMÓRIA preservada por ausência.

> Este restore **supersede** `relatorio_restore_20260727_174353.md`. Os artefatos `.json` /
> `.report.json` ficam **apenas em disco** (pasta `ref/`, gitignored). Este `.md` é o único
> item versionado desta etapa.

## Validação executada

| Gate | Resultado |
| --- | --- |
| `manage.py test home --parallel 4` (suíte completa, fixture regenerada) | **Ran 542 tests — OK** |
| `manage.py validate_tags` | **ERROR=0 · WARN=0 · INFO=0** |
| `json.load` + `deserialize` do fixture consolidado | 5061 / 5061 registros (100%) |
| `sincronizar_conteudo` em `transaction.atomic()` + `set_rollback(True)` | `mem_ok = true` (memória intacta) |
| Modelos de memória presentes no fixture | nenhum (`memory_models_in_fixture: []`) |
| Pass-2 pulado (preserva prod) | `TbRegiao, TbTerritorio, TbMapMarker, TbArmadilha, TbMapDesenho` |
| Line endings / BOM | CRLF / BOM=true |
| `home/fixtures/conteudo.json` regenerado (`dump_conteudo`) | 5244 registros de 26 modelos, carrega limpo no banco de teste |

**Contagem total:** 5061 registros (baseline 5061 → **0 líquidos**). Nenhuma inserção,
nenhuma remoção — a onda só **altera campos** de registros que já existiam.

## Diferenças vs baseline (cada uma explicada)

| Modelo | alterados | +ins | −rem | Causa |
| --- | ---: | ---: | ---: | --- |
| `tbitemmagico` | 327 (`nome` 251, `loja` 91) | 0 | 0 | **Renomes de itens mágicos** casados pela ponte EN (251) + **carona**: normalização de caixa da loja `'Somente Via Quest'` → `'Somente via Quest'` (91), aplicada por sessão paralela direto no banco. |
| `tbopcaojogo` | 14 (`tags_json`) | 0 | 0 | **Conjuração inata**: `at_will` derivado da descrição. |
| `tbclassehabilidade` | 6 (`tags_json`) | 0 | 0 | Idem (`at_will` em conjuração permanente). |
| `tbtracoracial` | 5 (`tags_json`) | 0 | 0 | Idem — inclui `uses{1, reset:long_rest}` movido para **dentro** de cada `cast{}` (desfaz a ambiguidade de duas magias sob um limite só). |
| `tbtalento` | 4 (`tags_json`) | 0 | 0 | Idem (as 4 Marcas Arcanas). |

### Renomes de itens mágicos (251) — slugs INTACTOS

O casamento foi feito pela ponte de nome em inglês; **nenhum `slug` mudou** (verificado:
0 slugs alterados entre banco e fixture anterior), então o merge por slug encontra a mesma
linha na produção e só troca o rótulo. Exemplos:

| Slug (inalterado) | De | Para |
| --- | --- | --- |
| `alfinete-harper` | Alfinete Harper | Broche dos Harpistas |
| `anel-de-armazenamento-de-feiticos` | Anel de Armazenamento de Feitiços | Anel de Armazenar Magias |
| `arma-viciosa` | Arma Viciosa | Arma Brutal |
| `lanterna-everbright` | Lanterna Everbright | Lanterna Sempre-Acesa |
| `tinta-moodmark` | Tinta Moodmark | Tinta Marca-Humor |
| `1-envoltorios-de-poder-desarmado` | +1 Envoltórios de Poder Desarmado | +1 Bandagens do Punho Poderoso |

### Conjuração inata (29 tags_json) — WARN `innate-cast-uses` zerado

O validador exige que todo `cast{… without{slot} …}` diga **quantas vezes**. As 29 linhas
ganharam `at_will` ou `uses{N, reset:R}` **derivados da própria descrição** — nenhuma regra
nova foi inventada. Duas correções acompanham no validador (`home/tag_engine/validator.py`):

1. o `N` de `uses{}` é **fórmula**, não átomo — `uses{ max(wis_mod,1), reset:long_rest }`
   tem vírgula dentro dos parênteses e antes era lido como "sem reset";
2. `cast{}` dentro de `instant{}` é **efeito roteirizado** da ativação que o contém (quem
   mede o uso é o `trigger=` / `resource_cost:` da feature) e deixa de exigir limite próprio.

### Carona intencional: caixa da loja (91)

A normalização `'Somente Via Quest'`/`'Somente Via quest'` → `'Somente via Quest'` foi
aplicada por **outra sessão** direto no banco de dev enquanto esta onda rodava. Como o
restore é um retrato do dev, ela entra junto — de propósito, e está registrada aqui e na
mensagem do commit. Após a normalização o catálogo tem **6 lojas distintas**: Alquimia (73),
Estábulos (4), Forja (177), Item Mágico (318), Joalheria (118), Somente via Quest (263).

## Reconciliação de PK do fixture — TbCosmetico (achado do gate)

O `dump_conteudo` regenerado **não carregava**:

```
IntegrityError: Could not load home.TbCosmetico(pk=31): UNIQUE constraint failed: TB_Cosmetico.Slug
```

Causa: o banco de dev **derivou** dos PKs canônicos. Os 6 temas basais semeados pela
migração `0057_backfill_seed_temas_basais` ficam em **23-28** num banco recém-migrado
(confirmado sondando um SQLite vazio migrado do zero), mas no dev estão em **31-36**. Como o
banco de teste nasce das migrações e só depois recebe o `loaddata`, o fixture com 31-36
colide no `UNIQUE(Slug)` com os 23-28 já semeados.

**O que foi feito:** os 6 registros de `TbCosmetico` do fixture (e as 6 entradas
correspondentes do manifesto) foram realinhados para **23-28**, que é exatamente o que o
fixture anterior já trazia. Nada mais mudou nesses registros — só o PK.

**Impacto zero na produção:** `TbCosmetico` está em `UPSERT_POR_SLUG` (`home/deploy_sync.py`),
ou seja, o merge casa por slug e **preserva o PK da produção**; o inventário
(`TbUsuarioCosmetico`) não é tocado. O PK do fixture só importa para o `loaddata` dos testes.

> **Pendência para o PO (fora do escopo desta onda):** o banco de dev continua com esses 6
> cosméticos em 31-36. Enquanto não for realinhado para 23-28, **toda regeneração futura do
> `conteudo.json` vai precisar da mesma correção manual**. O `UPDATE` no dev não foi aplicado
> aqui porque a ação foi barrada pelo sistema de permissões — é uma linha por tema
> (`UPDATE TB_Cosmetico SET id=<23..28> WHERE id=<31..36>`) e é segura: no dev
> `TbUsuarioCosmetico` e `TbConquista` (as duas únicas FKs para o modelo) estão **vazias**.

## Churn de PK conhecido (inócuo, herdado do baseline)

`TbMagia` mantém a permutação de PK já registrada no relatório anterior: dev tem
151=`sussurro-dissolvente`, 577=`estupefacao`, 578=`conjurar-celestial`,
580=`sussurros-dissonantes`, 581=`voragem`, enquanto o fixture anterior/manifesto traziam
outra ordem para os mesmos 5 slugs. **Não bloqueia:** `TbMagia` também é `UPSERT_POR_SLUG`,
então o merge de produção casa por slug e preserva o PK de lá — `TbPersonagemMagia.id_magia`
não se mexe. O manifesto regenerado passa a refletir a ordem do dev.

## Checklist de aplicação em produção (runbook)

1. **`force_update`** na produção (traz o código desta onda: moeda composta, wizard direto,
   validador de conjuração inata).
2. **Migrar antes do merge:** `python manage.py migrate home`. Esta onda **não** adiciona
   migração nova — a última continua sendo `0087_notas_jogador_onda_f`.
3. **Backup completo da produção** imediatamente antes do merge.
4. **Merge de conteúdo:** admin console → ação `merge_conteudo` apontando para
   `restore_consolidado_20260728_194351.json`. Upsert por slug; mundo/mapa e memória
   preservados.
5. **Rollback:** em caso de falha, restaurar `ref/backup_completo_20260722_230533.json`
   (`loaddata`).
6. **Smoke pós-merge:**
   - **Moeda composta:** carteira de 134 PC na ficha mostra as três caixinhas `1 | 3 | 4`
     (PO/PP/PC) e o title `1 PO 3 PP 4 PC`; nenhuma tela exibe `12,5 PO`.
   - **Venda no Mercado:** item mundano de `2 PO` credita `1 PO 6 PP` (80%).
   - **Wizard:** o passo de Atributo/Talento não tem botão "Escolher" — mexer no cartão já
     enfileira, e há **um cartão por aprimoramento pendente**.
   - **Renomes:** buscar "Broche dos Harpistas", "Arma Brutal" e "Lanterna Sempre-Acesa" na
     vitrine de itens mágicos (os nomes antigos não devem existir).
   - **Loja:** o filtro `Somente via Quest` agrupa os 263 itens numa única entrada.
   - **`validate_tags`:** roda até o fim com `ERROR=0 WARN=0`.

## Rastreabilidade

- Commit que produziu este estado (branch `dev`):
  `feat(site): onda leve pos-Ficha v2 — moeda composta, wizard direto e saneamento de conteudo`
- Fonte única da moeda: `home/moeda.py` (`decompor` / `moeda_display` / `preco_po_display`).
- Regra do validador de conjuração inata: `home/tag_engine/validator.py`
  (`_INNATE_USES_RE`, `_check_innate_casting_tags`), coberta por
  `home/test_tag_engine.py::InnateCastUsesTests`.
