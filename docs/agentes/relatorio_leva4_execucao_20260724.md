# Relatório — execução da parte pesada da 4ª leva + auditoria (2026-07-24)

> Fecho da rodada iniciada pelo briefing `docs/agentes/briefing_leva4_pesada.md`.
> A execução foi feita por agente executor em sessão própria (interrompida antes do
> commit) e auditada/completada nesta sessão. Tudo descrito aqui está commitado e
> pushado em `origin/dev`.

## Commits da rodada

| Commit | Conteúdo |
|---|---|
| `ecef27b` | **Picks de runtime fora do wizard** (item 1 do briefing): `pick:` dentro de `trigger=`/`instant{}`/`while_active{}` é escolha de USO (papel runtime) e não gera mais pendência de wizard/level-up — Máscara de Guerra, Aspecto Selvagem e Mordida Lacerante saíram das escolhas fixas. Escolhas antigas persistidas são ignoradas no readback (nada deletado). |
| `a77ecf9` | **Primeira parte da fetch-ificação da ficha** (item 4): mutações da edição de ficha via fetch. |
| `2395d26` | **Segunda onda pesada** (validada com gates reais antes do commit): level-up **multiclasse com contexto explícito de classe** (subclasse/truques/magias/troca por classe), **cotas de magia contabilizadas por classe** (Paladino não preenche cota de Feiticeiro), restante da edição de ficha via **fetch com fallback PRG** (inclui staffbox — partial `_ficha_concessoes_staff.html`), fix do `::toggle` do Markdown (Manifestação Mística renderizava como bloco de código), **comando `auditar_equipabilidade_itens`** + testes, **comando `export_restore_consolidado`** (gerador oficial e reproduzível do restore), motor **ignora `equipado=True` de item não-equipável** (preserva inventários sem conceder mecânica), relatório do restore `20260723_225159`. |
| `78f3488` | **Fix do Multitalentoso** (bug reportado pelo PO em print): o traço humano `pick:talento:1(from:any_raca, requires:prereq, no_asi)` deve conceder talento **GERAL** ("um Talento de qualquer raça para a qual cumpra os pré-requisitos", sem bônus de atributo). Causa dupla: (a) `_talento_universe` não reconhecia `from:any_raca` (universo caía no marcador de origem); (b) humano Erthari tem DOIS grupos `pick:talento` (Determinação Comum=origem, Multitalentoso=geral) e o apply pegava o primeiro do mesmo tipo — "Precisão" validava contra o universo só-de-origem → "fora do universo". Fix: `_TALENTO_GERAL_RE` (`from:any_raca`/`tipo:geral` → gerais com `_talento_prereq_ok`) + apply desambigua grupos pelo universo que contém o valor. Testes novos em `home/test_talento_humano.py`. |

## Gates (saídas reais da rodada)

- Suíte completa: **328 testes, OK** (323 na validação da onda + 5 novos do Multitalentoso).
- `manage.py validate_tags`: **ERROR=0 WARN=0 INFO=0** (3.479 registros, 8.740 linhas de tag).
- `manage.py check`: sem problemas.
- Invariantes do Scar no espelho preservados (FOR 19, desarmado +11 / `1d10 +8`,
  15 m / 50 ft, PV 148, CA 19 com escudo comum / 20 com `+1 Escudo (*)`).

## Conteúdo / deploy

- **Restore vigente:** `ref/backups/restore_consolidado_20260723_225159.json`
  (sha256 `c85a8a80...`; 5.011 registros; única mudança vs baseline `20260722_202656`
  = `TbItemMagico` com **266 slots corrigidos** pela auditoria de equipabilidade —
  ex.: `apito-da-aguia` → `item_menor`; 43 já corretos; **20 holds** de baixa confiança
  NÃO aplicados). Gerado por `manage.py export_restore_consolidado`.
- **Rollback:** `ref/backup_completo_20260722_230533.json`.
- **Aplicação:** código primeiro (`force_update.bat`, migrações incluídas) → backup
  completo pelo console → **Merge de conteudo (dev → produção)** com o restore acima.
  Nunca usar a restauração por PK. Detalhes: `docs/agentes/relatorio_restore_20260723_225159.md`.

## Auditoria briefing × executado

| Item do briefing | Status |
|---|---|
| 1. Picks de uso fora do wizard | ✅ `ecef27b` |
| 2. Auditoria dos equipáveis | ✅ 266 corrigidos; **20 holds esperando o PO** (`scratch/equipaveis_aplicacao_log.json`) |
| 3. Consumível ≠ recurso recuperável | ❌ **pendente** |
| 4. Fetch-ificar a ficha | ✅ `a77ecf9` + `2395d26` |
| 5. Subir de nível encadeado (N2→N3) | ❌ **pendente** |
| 6. Trocar maestria no descanso longo | ❌ **pendente** |
| 7. UX das escolhas (descrição completa + sem clique "Escolher") | ❌ **pendente** |
| 8. Housekeeping (rollback novo etc.) | ✅ |

**Extras entregues além do briefing:** contexto de classe no level-up multiclasse,
cotas de magia por classe, fix do `::toggle`, gerador oficial do restore.

## Próxima rodada (quando o PO liberar)

1. Itens 3, 5, 6 e 7 do briefing (que segue válido como especificação).
2. Decisão do PO nos 20 holds de equipabilidade.
3. Pendências de fora: itens fungal (fonte da staff), Axe Beak (bestiário),
   rework Vampiro/Bestial/Folken.
