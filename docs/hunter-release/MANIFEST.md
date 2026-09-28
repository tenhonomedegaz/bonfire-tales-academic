# Manifesto de revisao - hunter-release

**Pacote local em consolidacao para `dev`; sem push ou deploy.** O backup JSON de reconciliacao prometido pelo usuario ainda nao foi fornecido.

## Repositorio

- Branch local `dev`, upstream `origin/dev`, base `d3cb0cc814bc88eaecf1d9c7375dacfc05a5a4ef`; candidato `draft/hunter-release-r153` em `4fd0678f02e6d99278097fd32291fa5f48edc5af`.
- Remote configurado: `https://github.com/bonfiretales-dev/BonfireSite.git`.
- 232 caminhos locais alterados/novos inventariados, incluindo o manifesto.
- Pipelines encontrados (.github/workflows, Procfile, render.yaml, railway.json, Jenkinsfile, .gitlab-ci.yml): nenhum.
- `deploy_conteudo.bat` existe, mas nao identifica nem autoriza o alvo de producao.

## Classificacao

[manifest.json](manifest.json) lista caminhos, SHA-256 e motivos. Apenas o hash do proprio JSON e omitido.
- `candidato_cacador`: 95.
- `compartilhado_revisar_diff`: 36.
- `dependencia_obrigatoria`: 54.
- `fora_do_marco_vtt`: 2.
- `melhoria_existente_revisar`: 45.

Arquivos compartilhados como views.py, urls.py e models.py exigem revisao por diff para separar mudancas alheias. O VTT permanece fora do marco.

## Seleção local para commit

O índice Git temporário `scratch/evolucao-q14/release-index-r153` contém 229
caminhos selecionados do manifesto. O índice normal e o worktree permanecem
intactos. Ficaram fora `home/vtt.py`, `home/test_vtt_integration.py` e a alteração
tipográfica alheia em `docs/agentes/regras_retagging_tags_json.md`. Nos blobs
selecionados de `bonfire/settings.py` e `home/urls.py`, foram removidos apenas as
configurações, a importação e as rotas do VTT; as alterações do Caçador e demais
melhorias foram mantidas. Os SHA-256 em `manifest.json` descrevem o worktree,
portanto esses dois blobs selecionados diferem dos hashes ali listados; a árvore
Git produzida pelo índice temporário identifica o pacote candidato exato.

O pacote candidato passou em `git diff --cached --check` usando o indice
temporario e em `manage.py check` apos extracao da arvore para uma copia
isolada. O commit `4fd0678` existe apenas na branch local de revisao; nao
houve push nem deploy. Antes do commit definitivo em `dev`, revisar o diff
e a arvore exata apos atualizar este manifesto.

## Migracoes

| Arquivo | Dependencias declaradas |
|---|---|
| `home/migrations/0103_resource_command_receipts.py` | `[('home', '0102_mercado_treinamentos_emprestimos')]` |
| `home/migrations/0104_immutable_content_rulesets.py` | `[('home', '0103_resource_command_receipts'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]` |
| `home/migrations/0105_immutable_content_guards.py` | `[('home', '0104_immutable_content_rulesets')]` |
| `home/migrations/0106_hunter_preparation.py` | `[('home', '0105_immutable_content_guards')]` |
| `home/migrations/0107_hunter_mark.py` | `[('home', '0106_hunter_preparation')]` |
| `home/migrations/0108_hunter_companion.py` | `[('home', '0107_hunter_mark')]` |
| `home/migrations/0109_hunter_awakening.py` | `[('home', '0108_hunter_companion')]` |
| `home/migrations/0110_hunter_exorcist.py` | `[('home', '0109_hunter_awakening')]` |
| `home/migrations/0111_hunter_traveler.py` | `[('home', '0110_hunter_exorcist')]` |
| `home/migrations/0112_hunter_mutagens.py` | `[('home', '0111_hunter_traveler')]` |
| `home/migrations/0113_hunter_regularization.py` | `[('home', '0112_hunter_mutagens')]` |

## Portoes restantes

- Fluxos do Caçador validados no criador, laboratório, level-up e ficha, incluindo Familiar de Batalha da fonte `ref/FAMILIAR_DE_BATALHA.md` (46 testes integrados e 20 testes complementares aprovados no PostgreSQL isolado). O cadastro da magia na fixture é reproduzível com `python manage.py prepare_battle_familiar`; a publicação no banco real ainda depende dos portões abaixo.
- Escolhas legadas sem equivalencia verificavel permanecem bloqueadas na regularizacao; fichas antigas preservam a revisao. Transferencias exatas exigem confirmacao e a aplicacao verifica patrimonio, magias, inventario e historico.
- Catalogo composto/reexecutado com IDs do ambiente; IDs da fixture nao sao IDs autorizados de producao.
- Aceite integrado no PostgreSQL isolado `test_hunter_r148`: 81 testes dos fluxos
  combinados (Caçador, Familiar de Batalha, criador, catálogo, derivações,
  opções, ficha de magias e pathbuilder) aprovados. Na suíte de todos os módulos
  `test_hunter_*`, 226 de 227 passaram inicialmente; o caso restante tinha
  expectativa obsoleta de três Ordens com Segredo exclusivo no nível 18, embora
  a referência e o catálogo versionado contenham oito. A expectativa foi
  corrigida e o caso, junto dos nove testes de referência do rework, passou
  (10/10); nenhuma implementação mudou após a suíte ampla. O cliente de
  pathbuilder passou em 18/18 testes de navegador com Playwright 1.62 e
  Chromium local. `migrate --check` e `preflight_hunter_release` passaram no
  banco de teste (sem migrações pendentes, tabelas ausentes ou FKs inválidas).
  `sync_conteudo --dry-run` terminou sem escrita; relatou uma exclusão explícita
  de conteúdo ausente (`TbMagia.sacrificio-de-sangue`), a revisar no destino real.
- Alvo local autorizado: branch `dev` e PostgreSQL em `localhost:5432`, banco `postgres`, esquema `public`, endereco efetivo `::1/128`, diretorio de dados local `C:/Users/helio/Desktop/Projetos Bonfas/pgsql/data`. Nao ha autorizacao de push/deploy.
- Em 28/09/2026, backup custom fresco `scratch/evolucao-q14/local_pre_hunter_20260928_003348.dump` (SHA-256 `f8e3b26d874859034272fc62021c3ae804b8f087873f4ce71c819d977002803a`) foi restaurado no banco isolado `bonfire_r154_restore_20260928_003348`: 80 tabelas com contagens e assinaturas de linhas iguais, 0 FKs nao validadas. O cliente PostgreSQL 18 exigiu suprimir `SET transaction_timeout` no SQL de restauracao para o servidor local; a comparacao integral passou.
- No banco local foram aplicadas `home.0103` a `home.0113`; `migrate --check` e o preflight apos migracao passaram. Seis Ordens legadas (IDs 21, 112, 115-118) ficaram intactas; oito Ordens novas receberam IDs 152-159 com slugs `-rework`. `Battle Familiar` recebeu ID 582 e a revisao selada do Cacador ID 3, checksum `00d9539eb5625c342d1aada834fc4c7a5cd87e2ef9a6ace5e746d35f88cb5bde`. Reexecucao criou 0 Ordens, 0 magias e reutilizou a revisao. A ativacao local usa somente a configuracao ignorada `.env`; nenhuma ficha foi convertida (o banco local tinha 0 personagens).
- `sync_conteudo --dry-run` foi executado sem escrita; o tombstone `TbMagia.sacrificio-de-sangue` estava ausente. O sync completo inclui `delete`/reinsercao de tabelas auxiliares e nao foi executado sob a autorizacao atual de operacoes sem exclusoes.
- Backup JSON de reconciliacao, push e destino remoto seguem pendentes e separados do commit local.
- Procedimento de banco e retorno: [POSTGRESQL.md](POSTGRESQL.md).

## Preparacao do commit

Apos revisao e testes, selecionar explicitamente `git add -- <caminho-aprovado>`. Arquivos mistos exigem selecao de hunks. Conferir `git diff --cached --name-status` e `git diff --cached`. Nao usar `git add .`; nao incluir VTT. Recalcular hashes apos qualquer alteracao. O índice temporário permite conferir o candidato sem contaminar o índice normal; ele não substitui a revisão de um commit definitivo.

Uma branch local `draft/hunter-release-r153` guarda o candidato inicial.
O banco local autorizado recebeu migracoes aditivas e conteudo especifico
do Cacador; nenhuma regularizacao em massa ocorreu. Push, deploy remoto e
restauracao do JSON futuro nao foram executados.
