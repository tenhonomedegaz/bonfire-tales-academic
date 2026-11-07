# Readiness do builder: DEV e atualização manual posterior

Estado: **checklist para execução, não aceite de release**. Critérios F1–F6 e
evidências de paridade: [BUILDER_RELEASE_CLOSEOUT.md](BUILDER_RELEASE_CLOSEOUT.md).
Não repetir aqui a auditoria editorial de classes.

## Fotografia inspecionada em 14/10/2026

- Branch `dev`, HEAD `fe1ebb4ce81d8e3e56e3bde74ca93bed65624586`.
- `git diff --no-ext-diff | git hash-object --stdin` dos arquivos rastreados:
  `f9b6ba4263486881e483ce7d11bf6d5cd87cd19b`. Havia 21 arquivos
  rastreados modificados (4.781 inserções, 145 remoções); `docs/qa/` era
  não rastreado. Esse hash **não inclui** os arquivos não rastreados.
- O diff rastreado abrangia motor, views, builder, level-up, JavaScript,
  templates, testes e `home/fixtures/conteudo.json`. Não havia migration
  modificada ou nova no `git status` observado; a última migration encontrada
  na árvore foi `home.0151_tbentregaeventoconquista`. Isto não comprova o estado
  de migrations aplicadas em DEV ou produção.
- `git diff --check` retornou código 0 nesta fotografia. Não foram executados
  testes, `manage.py check`, consultas ao banco, migrações ou deploy nesta frente.
  Outro agente edita dados/tags em paralelo: revalidar status, diff, fixture e
  evidências após integrar suas alterações.

## Portão de integração e QA final em DEV

Executar **após** o fechamento editorial/paridade F1–F3, com o Python do
ambiente do projeto e PostgreSQL DEV identificado. Registrar saída, código de
retorno, HEAD e novo hash do diff no aceite F4. `manage.py test` usa banco de
teste: confirmar previamente que a conexão seleciona o ambiente DEV.

```powershell
git status --short --untracked-files=all
git rev-parse HEAD
git diff --stat
git diff --no-ext-diff | git hash-object --stdin
git diff --check
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py test home.test_pathbuilder home.test_pathbuilder_spells home.test_levelup home.test_hunter_public_creator home.test_hunter_companion home.test_versioned_options home.test_versioned_origins home.test_deploy_sync --noinput
.\.venv\Scripts\python.exe manage.py test home --noinput
```

O último comando é o gate geral F4, **uma vez** após integrar as mudanças;
repetir apenas testes dos consumidores afetados por correções posteriores.
Conferir manualmente criação, progressão/regressão, escolhas, salvar/reabrir,
fichas legadas e multiclasse suportada contra a matriz e fontes independentes
citadas no closeout. Os JSONL e a baseline de 13/10 são inventário histórico,
não resultado final. Regerar/revalidar a matriz quando dados, código ou
revisões relevantes mudarem; não atribuir paridade por contagem de alertas.

## Conteúdo versionado e entrega DEV (F5)

1. Conferir no PostgreSQL DEV a identidade do banco e o estado de migrations.
   A árvore não traz migration nova nesta fotografia; `migrate --plan` no alvo
   é o dado decisivo. Se houver pendência, revisar cada operação antes de
   executar `migrate --noinput` no ambiente autorizado.
2. Comparar o fixture versionado com o conteúdo DEV aprovado. Se necessário,
   gerar **no DEV** com o comando existente
   `.\.venv\Scripts\python.exe manage.py dump_conteudo --output home/fixtures/conteudo.json --manifest home/fixtures/conteudo_manifest.json`;
   revisar também `home/content_deletions.json` e `home/content_renames.json`.
   O manifesto é verificação de PK→chave, não identidade transferível à produção.
3. Revisar `git status --short --untracked-files=all` arquivo a arquivo e
   incluir no commit somente a entrega aprovada: código, templates, JS, testes,
   fixture/manifest efetivamente atualizados, docs de fechamento e este roteiro.
   Avaliar explicitamente `ARQUITETURA_EVOLUCAO_BONFIRE.md` e cada arquivo de
   `docs/qa/`; não usar `git add .` neste worktree sujo. A matriz compactada,
   JSONL e scripts de triagem entram apenas se forem evidência final necessária
   e revisada; artefatos históricos ou temporários não entram por inércia.
4. Excluir backups/dumps locais, `ref/`, `scratch/`, `.env`, segredos, logs,
   SQLite de triagem (`docs/qa/builder-release-triage-2026-10-13.sqlite3`),
   arquivos de produção e mudanças alheias. Não usar `loaddata` com o fixture
   de catálogo. Revisar o staged diff e seus nomes antes do commit.
5. Depois de F4 aprovado: commit e push **normal** em `dev`; confirmar SHA do
   commit local e remoto. Entregar ao operador o SHA, migration plan, estado do
   fixture e instruções de pull/ativação. Push DEV não aciona publicação.

## Publicação manual posterior (F6)

Este marco depende de confirmação do usuário para atualizar produção e de
identificação do alvo/ambiente de hospedagem. O processo real de pull, restart,
coleta de estáticos e smoke HTTP deve ser confirmado com o operador; não foi
identificado por esta inspeção. Sequência mínima a preparar:

1. Fixar o SHA aprovado; confirmar que o servidor usa esse commit, dependências
   de `requirements.txt`, configuração Django e variáveis de banco. Em
   `bonfire/settings.py`, `POSTGRES_URL` tem prioridade; sem ela são usadas
   `DB_*`. `DATABASE_URL` não seleciona o banco deste projeto. Não imprimir
   URL, senha nem chave de API. Obter identidade sem segredo via
   `python manage.py preflight_hunter_release` no PostgreSQL autorizado:
   host, porta, banco, usuário, contagens, migrations pendentes, tabelas ausentes
   e FKs não validadas. O comando é somente leitura; a identidade da produção
   prevalece sobre IDs locais.
2. Revisar `python manage.py migrate --plan` e
   `python manage.py sync_conteudo --dry-run` **nesse alvo**. O dry-run informa
   quantidades do fixture e estado dos tombstones; não garante que o sync
   completo será seguro. Inspecionar `home/content_deletions.json` e
   `home/content_renames.json`, colisões de slug/PK, revisões imutáveis,
   publicações e fichas ligadas ao catálogo. `--allow-content-deletions`
   exige autorização operacional separada.
3. Antes de mutações, verificar integridade e espaço, fazer backup PostgreSQL
   completo fresco e ensaiar `pg_restore --exit-on-error` em **novo banco
   isolado**, comparando contagens, assinaturas e vínculos. Ensaiar as operações
   aprovadas nessa cópia. Referência detalhada:
   [POSTGRESQL.md](../hunter-release/POSTGRESQL.md). O arquivo
   `deploy_conteudo.bat` encadeia `migrate --noinput` e `sync_conteudo`, mas não
   identifica o alvo nem ensaia restauração; não é um portão de segurança.
4. Com alvo e plano autorizados, instalar o código, aplicar apenas migrations
   aprovadas e fazer a atualização de conteúdo escolhida após o ensaio.
   `sync_conteudo` faz upsert por slug em tabelas referenciadas por usuários,
   preservando PK de produção; substitui outras tabelas por exclusão e reinserção.
   Fluxos especiais do Caçador têm procedimento próprio e podem **proibir** o
   sync completo: conferir [GUIA_APLICACAO.md](../hunter-release/GUIA_APLICACAO.md)
   e [RECONCILIACAO_PRODUCAO.md](../hunter-release/RECONCILIACAO_PRODUCAO.md)
   contra o estado real antes de combinar pacotes. Ver também
   [deploy-sync-conteudo.md](../deploy-sync-conteudo.md).
5. Manter chaves, auditoria e idempotência da API, vínculos de publicação de
   classe, preços, mapa/wiki, dados comunitários e memória de usuários como
   estado do destino. As migrations `0122`–`0124` criam API/publicação/pinning,
   mas não significam que a publicação de classe foi ativada. A operação
   `class-revision` não publica por si; `class-publication` exige escopo próprio,
   backup configurado e alvo verificado. Não transportar IDs de classe,
   ruleset, chave ou checksum de DEV como se fossem identidades de produção.
   Referência: [db_access.md](../db_access.md) e
   [bonfire_db_api_integration.md](../bonfire_db_api_integration.md).
6. Após a atualização manual, validar API sobre HTTPS sem expor token, páginas
   públicas, criador, level-up, fichas antigas e multiclasse, salvar/reabrir,
   contagens/assinaturas protegidas e logs. Registrar SHA publicado, operações,
   resultado e plano de retorno. Sem smoke remoto e comparação dos dados,
   F6 permanece não verificado.

## Pendências desta fotografia

Paridade final F4, resultado da suíte geral, estado de migrations em cada banco,
alinhamento do fixture/manifest, destino e processo de produção, backup
restaurável e smoke remoto **não foram verificados**. Revalidar esta fotografia
após o trabalho paralelo antes de decidir commit ou release.
