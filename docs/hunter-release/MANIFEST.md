# Manifesto de revisao - hunter-release

**Pacote consolidado na branch local `dev` em `508673e8bf7f61326448e8c3869dda21a91bdece`; sem push ou deploy.** O backup JSON de producao foi fornecido e permanece intacto. A reconciliacao foi ensaiada somente em banco isolado.

## Repositorio

- Branch local `dev`, upstream `origin/dev`, commit consolidado `508673e8bf7f61326448e8c3869dda21a91bdece`; candidato anterior `draft/hunter-release-r153` em `4fd0678f02e6d99278097fd32291fa5f48edc5af`.
- Remote configurado: `https://github.com/bonfiretales-dev/BonfireSite.git`.
- 232 caminhos locais alterados/novos foram inventariados; 229 caminhos selecionados integraram o commit local. Alteracoes VTT e documentos alheios ficaram fora.
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

O pacote passou em `git diff --cached --check` usando o indice temporario e
em `manage.py check` apos extracao da arvore para uma copia isolada. A arvore
selecionada foi integrada no commit local `508673e8` em `dev`. Nao houve push
nem deploy.

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
- O JSON `ref/backups/backup_completo_20260928_010338.json` e um backup de dados de producao, SHA-256 `a6a674829b8d46f01d8d3966b31bf0e7ca049cd3df597a23ab0b17d013222227`. Seus 8.305 registros foram restaurados com PKs originais em copia local isolada; 54 modelos conferidos e nenhuma FK nao validada.
- A primeira fixture de 2.384 insercoes priorizava IDs locais e remapeava seis PKs do JSON. Ela foi substituida pela orientacao de producao como fonte de verdade e **nao deve ser aplicada**.
- O novo artefato ignorado pelo Git `ref/backups/reconciliacao_producao_rework_20260928.json` adiciona somente 50 registros de conteudo aprovados (oito Ordens, Familiar de Batalha e revisoes/regras versionadas), sem remapear PKs de producao. Ensaio em copia isolada: 8.305 linhas de producao intactas em 85 tabelas, 29 personagens preservados, nenhuma ficha convertida, 0 FKs nao validadas e segunda passada calculada com 0 insercoes. As sequencias conferidas apontam para o maior PK presente. Uma divergencia de item magico local foi excluida; prevalece o dado de producao.
- A aplicacao do JSON ou do novo artefato fora da copia isolada nao ocorreu. Dados locais que nao pertencem ao rework, inclusive uma conta local com PK colidente, precisam de mapeamento e decisao separados. Push, deploy e migracao em producao nao foram autorizados.
- Procedimento de banco e retorno: [POSTGRESQL.md](POSTGRESQL.md).

## Registro do commit local

O commit 508673e8bf7f61326448e8c3869dda21a91bdece foi montado com selecao explicita de 229 caminhos e revisao do indice temporario, sem incluir VTT nem alteracoes alheias. Os artefatos JSON de backup e reconciliacao ficam ignorados pelo Git por conterem dados privados; nao pertencem ao commit.

Uma branch local `draft/hunter-release-r153` guarda o candidato inicial.
O banco local autorizado recebeu migracoes aditivas e conteudo especifico
do Cacador; nenhuma regularizacao em massa ocorreu. O JSON recebido foi
ensaiado em copia local isolada, sem aplicacao ao banco local configurado
ou ao banco de producao. Push e deploy remoto nao foram executados.
