# PostgreSQL do pacote do Caçador

Este procedimento exige identificar o ambiente e obter autorização operacional
específica antes de qualquer migração, sincronização ou troca de banco real.
`bonfire/settings.py` lê `POSTGRES_URL` (ou as variáveis `DB_*` quando ela não
existe). `DATABASE_URL` não seleciona o banco deste projeto.

## Preflight

Executar `manage.py preflight_hunter_release` para obter JSON com a identidade
real da conexão (sem senha), contagens, migrações aplicadas/pendentes, tabelas
ausentes e FKs não validadas. A leitura usa transação PostgreSQL somente de
leitura e snapshot consistente. O comando não migra nem sincroniza conteúdo;
tabelas ausentes ou FKs não validadas produzem saída de erro. Migrações pendentes
são relatadas para revisão, pois são esperadas antes da atualização.
Esse inventário não substitui as assinaturas dos dados, o ensaio de restauração,
a comparação das fichas ou a autorização do alvo abaixo.

1. Fixar `POSTGRES_URL` para o banco autorizado. Confirmar `NAME`, `HOST`, `PORT`
   e `USER` pela configuração Django carregada e confirmar `connection.vendor`.
   Não imprimir a URL completa nem a senha.
2. Registrar contagens e assinaturas das tabelas de personagens, patrimônio,
   magias, ledger, conteúdo e `django_migrations`; verificar integridade e
   espaço para backup e restauração.
3. Executar `manage.py migrate --plan` e `manage.py sync_conteudo --dry-run`.
   Inspecionar os tombstones. `--allow-content-deletions` requer autorização
   separada; não faz parte da aplicação padrão.
4. Fazer `pg_dump --format=custom` do banco completo e testar `pg_restore
   --exit-on-error` em um **novo banco isolado**, sem `--clean`. Comparar contagens,
   assinaturas e migrações com a origem antes de alterar o alvo.
5. No banco restaurado isolado, ensaiar somente as adicoes versionadas e
   aprovadas do Cacador. Revalidar identidades, PKs, FKs, assinaturas das
   linhas anteriores, personagens legados, sequencias e idempotencia. O dry-run
   classifica tombstones, mas nao autoriza o sync completo nem substitui o ensaio.

## Aplicação autorizada

Apos preflight e autorizacao especifica do alvo, aplicar apenas migracoes
aditivas e conteudo revisado contra o estado atual. Reexecutar migrate --check,
conferir que nenhuma linha anterior mudou e validar personagens, patrimonio,
magias, ledger e conteudo antes de habilitar os fluxos novos. O sync completo
substitui tabelas auxiliares e nao integra este procedimento.

Sequência de comandos no ambiente **já identificado e autorizado**, com
`POSTGRES_URL` fornecida por mecanismo seguro e conferida no preflight:

```text
python manage.py preflight_hunter_release
python manage.py migrate --plan
python manage.py sync_conteudo --dry-run
pg_dump --format=custom --file=<backup_fresco> --dbname=<conexao_autorizada>
pg_restore --exit-on-error --dbname=<novo_banco_isolado> <backup_fresco>
# Comparar contagens/assinaturas e ensaiar apenas adicoes no banco restaurado.
python manage.py migrate --noinput
python manage.py migrate --check
# NAO executar sync_conteudo neste pacote: o comando pode substituir tabelas.
# Aplicar somente as adicoes revisadas apos novo preflight e autorizacao do alvo.
python manage.py preflight_hunter_release
```

Não aplicar `--allow-content-deletions` na sequência padrão. No ensaio local, o
dry-run apontou o tombstone `TbMagia.sacrificio-de-sangue` como ausente; a
classificação no destino real precisa ser revisada antes do sync. O arquivo
`deploy_conteudo.bat` não confirma identidade do alvo nem ensaia restauração,
portanto não substitui estes portões. A troca de código e o smoke HTTP dependem
do pipeline e do ambiente de hospedagem ainda não identificados.

## Retorno seguro

- Antes de haver novas escritas no pacote, a restauração do dump **em outro
  banco** permite voltar ao estado anterior mediante troca coordenada de código
  e conexão. Não sobrescrever nem apagar o banco alterado.
- Depois de haver novas fichas ou regularizações, restaurar o dump anterior
  perderia essas escritas. Manter o esquema aditivo, suspender as operações
  afetadas e corrigir adiante; qualquer retorno de código precisa ser testado
  contra essas fichas. Não reverter `home.0113` para descartar a coluna JSON.

O alvo real, o procedimento de troca, o backup fresco e as autorizações devem
constar no manifesto de release antes do deploy.

## Aplicação local autorizada em 28/09/2026

O usuário autorizou somente o PostgreSQL local do projeto e o commit em `dev`.
A conexão confirmada foi `localhost:5432` (`::1/128`), banco `postgres`, esquema
`public`, com diretório de dados no próprio computador. Antes das escritas,
`pg_dump` gerou o backup e a restauração isolada descritos em [MANIFEST.md](MANIFEST.md);
80 tabelas tiveram contagens e assinaturas iguais e não havia FKs não validadas.
O cliente `pg_dump`/`pg_restore` 18 é mais novo que o servidor local: para o ensaio,
o SQL extraído do dump custom perdeu somente `SET transaction_timeout = 0;`.
Não houve restauração sobre o banco original.

Foram aplicadas apenas as migrações aditivas `home.0103` a `home.0113`.
As oito Ordens novas foram criadas com slugs técnicos `-rework`, deixando as seis
identidades antigas intactas. A magia `Battle Familiar` e o ruleset completo foram
adicionados por identidade verificada; a repetição reutilizou as mesmas IDs e
checksum. A seleção local da revisão está no `.env` ignorado pelo Git. Nenhuma
ficha existente foi convertida; o banco local não continha personagens.

`sync_conteudo --dry-run` foi executado, mas o sync completo não foi aplicado:
ele substitui outras tabelas por `delete`/reinserção e ultrapassaria a autorização
de operações sem exclusões. A atualização local necessária ao Caçador foi feita
por insercoes especificas e reexecutaveis. O JSON de producao foi recebido e
ensaiado em copia isolada, mantendo PKs, personagens e dados anteriores.
O roteiro atual de reconciliacao esta em RECONCILIACAO_PRODUCAO.md.

## Complemento multiclasse e ativacao local

Um Caçador legado do JSON de producao tem outra classe. Com o ruleset inicial de
nove entradas, a prévia de regularizacao falha ao resolver a revisao dessa classe.
Por isso, o pacote inclui o complemento aditivo
`ref/backups/reconciliacao_producao_multiclasse_20260928.json` (12 revisoes de
classe, um ruleset e 21 vinculos). O alvo precisa validar primeiro a fixture de
50 linhas, depois a de 34, sem atualizar linhas existentes. O ruleset de 21
entradas, checksum `90e74e8d6096c07b212e015daf2e96c3caff1f2333cb8674d795f8fd2882edd2`,
e a base do complemento. A revisao das caracteristicas basicas abaixo precisa
ser composta antes de configurar `HUNTER_CREATOR_RULESET_CHECKSUM` para novas
fichas. Nao converter fichas antigas em massa.

No PostgreSQL local `postgres`, antes do complemento, foi feito backup custom
fresco `scratch/evolucao-q14/local_pre_multiclass_20260928_024240.dump`,
restaurado em `bonfire_r157_restore_20260928_024240`. As 6.528 linhas em 85
tabelas coincidiram por assinatura. A carga de 34 linhas foi ensaiada nessa
restauracao e aplicada ao banco local com todas as linhas anteriores preservadas,
zero FK nao validada e zero insercao necessaria numa segunda passada. A `.env`
local ignorada pelo Git aponta agora ao checksum da revisao corrigida abaixo. O JSON de producao
nao foi carregado no banco local configurado. Nele, os 50 registros iniciais
do rework ja existiam por preparacao aditiva anterior e somente as 34 linhas
do complemento foram carregadas agora. Nada foi aplicado em producao.

Depois de preparar as adicoes iniciais do Cacador em um alvo identificado e
autorizado, compor a revisao completa sem escrever para conferir o catalogo:

```text
python manage.py compose_hunter_multiclass_ruleset --base-checksum 00d9539eb5625c342d1aada834fc4c7a5cd87e2ef9a6ace5e746d35f88cb5bde --expected-checksum 90e74e8d6096c07b212e015daf2e96c3caff1f2333cb8674d795f8fd2882edd2
```

O mesmo comando com `--apply` so pertence a uma operacao especificamente
autorizada, apos backup/restauracao e ensaio. Ele falha e reverte a transacao
se o checksum calculado diferir; a ativacao por configuracao vem depois.

## Correcao das caracteristicas basicas do Cacador

O HTML exige Destreza 13 **e** Sabedoria 13 para multiclasse em Cacador e
concede armadura leve, armas marciais e uma pericia da lista da classe. O
ruleset anterior congelou requisitos/proficiencias diferentes. A linha viva
`TB_Classe` fica intacta para fichas legadas; uma nova revisao imutavel altera
somente a copia de `class-catalog:<ID do Cacador>`. Nao converter personagens.

No PostgreSQL local autorizado, o backup fresco
`scratch/evolucao-q14/local_pre_hunter_basics_20260928_033736.dump` foi
restaurado em `bonfire_r160_restore_20260928_033736`: 85 tabelas e 6.562
linhas identicas por assinatura, sem FK invalida. A composicao nessa copia e
no banco local retornou o mesmo checksum
`da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289`;
a segunda execucao reutilizou o mesmo ruleset. No banco local, somente uma
revisao, um ruleset e 21 vinculos foram acrescentados; 0 personagens alterados.
A `.env` local ignorada pelo Git aponta ao novo checksum.

No destino **identificado e autorizado**, depois de aplicar o complemento de
21 entradas, executar primeiro sem `--apply` e conferir o checksum. Ensaiar
com `--apply` numa restauracao isolada antes de repetir no alvo autorizado:

```text
python manage.py compose_hunter_class_basics --base-checksum 90e74e8d6096c07b212e015daf2e96c3caff1f2333cb8674d795f8fd2882edd2 --expected-checksum da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289
```

Depois de `--apply` no alvo autorizado e de validar personagens, patrimonio,
magias e FKs, configurar `HUNTER_CREATOR_RULESET_CHECKSUM` com o novo checksum.
Para retorno de codigo, conservar as duas revisoes e os vinculos de personagens
ja criados; nao apontar uma ficha nova para a revisao antiga nem remover dados.
O ensaio na copia do JSON de producao preservou quatro Cacadores legados e
8.314 linhas anteriores em 82 tabelas fora do versionamento.
