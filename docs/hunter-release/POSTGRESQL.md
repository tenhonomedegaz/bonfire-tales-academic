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
5. No banco restaurado isolado, executar a sincronização completa do catálogo
   e repeti-la. Conferir a identidade de `Battle Familiar`, zero novas inserções
   na segunda execução, assinaturas das tabelas de memória e conteúdo comunitário,
   `migrate --check` e o preflight após a sincronização. O `--dry-run` apenas
   classifica contagens e tombstones; não substitui este ensaio.

## Aplicação autorizada

Após o preflight e a autorização do alvo, aplicar as migrações, reexecutar
`manage.py migrate --check` e confirmar que uma segunda execução não tem
operações pendentes. Sincronizar conteúdo somente após revisar o dry-run e as
exclusões explícitas. Conferir as invariantes de personagens, patrimônio,
magias, ledger e conteúdo antes de habilitar os fluxos novos.

Sequência de comandos no ambiente **já identificado e autorizado**, com
`POSTGRES_URL` fornecida por mecanismo seguro e conferida no preflight:

```text
python manage.py preflight_hunter_release
python manage.py migrate --plan
python manage.py sync_conteudo --dry-run
pg_dump --format=custom --file=<backup_fresco> --dbname=<conexao_autorizada>
pg_restore --exit-on-error --dbname=<novo_banco_isolado> <backup_fresco>
# Comparar contagens/assinaturas e ensaiar a sincronização no banco restaurado.
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py sync_conteudo
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
por inserções específicas e reexecutáveis. O backup JSON que o usuário fornecerá
depois do commit exige reconciliação própria por identidades e ensaio isolado;
ele não autoriza sobrescrever o banco local.
