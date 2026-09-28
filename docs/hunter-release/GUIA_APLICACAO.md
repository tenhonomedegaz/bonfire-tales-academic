# Aplicacao do rework e recuperacao de backup

## Qual operacao esta sendo feita

Atualizar uma producao que ja funciona NAO exige restaurar seu backup completo.
O backup e a base de ensaio e recuperacao; restaurar um JSON antigo sobre a
producao atual pode sobrescrever progresso dos jogadores.

O console administrativo, acao `restore_backup` em `home/admin.py`, desserializa
objetos Django e executa `obj.save()` dentro de uma transacao, depois realinha
sequencias. Isso e UPSERT POR PK, nao reconciliacao por identidade. A protecao
contra fixtures somente de conteudo nao torna um arquivo misto seguro.
Nao usar esse painel para aplicar os artefatos abaixo.

`Merge de conteudo` tambem nao e apropriado para este pacote: `deploy_sync`
substitui integralmente algumas tabelas auxiliares e trata rulesets como memoria.
Nao executar `sync_conteudo` completo para instalar este rework.

## Arquivos privados existentes

Todos ficam em `ref/backups/`, fora do Git:

1. `backup_completo_20260928_010338.json`: original de producao, referencia
   imutavel; NAO carregar sobre uma producao que recebeu escritas posteriores.
2. `reconciliacao_producao_rework_20260928.json`: 50 adicoes revisadas.
3. `reconciliacao_producao_multiclasse_20260928.json`: 34 adicoes complementares.
4. `reconciliacao_producao_plano_20260928.json`: relatorio, NAO fixture.

Os arquivos `reconciliacao_insercoes_20260928_010338.json` e
`reconciliacao_plano_20260928_010338.json` foram SUBSTITUIDOS. O plano antigo
adaptava PKs de producao ao local e NAO deve ser aplicado.

Nao existe um JSON unico universal pronto para restaurar qualquer banco.
As duas fixtures foram ensaiadas contra o backup especifico de 28/09; PKs livres
nessa copia podem estar ocupados hoje. Sao insumos de reconciliacao, nao um
importador com verificacao automatica de conflitos.

## Metodo recomendado: shell de manutencao + copia PostgreSQL isolada

1. Identificar host, banco, schema e commit reais. Suspender escritas durante
   a aplicacao e obter backup fresco completo com `pg_dump` em formato custom.
   Conferir que o backup inclui as tabelas compartilhadas com o bot.
2. Restaurar esse dump em OUTRO banco vazio com `pg_restore --exit-on-error`,
   usando ferramentas compativeis com a versao PostgreSQL. Nao usar `--clean`
   no banco de producao. Falhas de restauracao precisam ser resolvidas antes
   de prosseguir; o JSON do admin nao substitui o dump completo.
3. Na copia, apontar explicitamente `POSTGRES_URL`, instalar o codigo/dependencias
   do commit escolhido, revisar `python manage.py migrate --plan` e ensaiar
   as migracoes. `python manage.py preflight_hunter_release` inspeciona o alvo.
   A branch dev inclui outras entregas alem do Cacador; revisar todas migracoes
   pendentes, nao presumir que termina em home.0113.
4. Comparar as duas fixtures, na ordem rework e multiclasse, com a copia atual.
   Preservar TODOS os PKs, valores e relacionamentos de producao. Identidade
   existente deve coincidir integralmente; conflito exige regenerar/remapear
   somente os registros locais novos e suas FKs. Nao aplicar `loaddata`
   cegamente: ele pode atualizar uma linha existente. Ensaiar a carga somente
   apos essa verificacao e conferir sequencias, FKs e assinaturas das linhas
   anteriores; repetir deve inserir zero registros.
5. As duas fixtures deixam o ruleset composto anterior. Aplicar tambem a
   correcao FINAL de requisitos/proficiencias de multiclasse, inicialmente
   sem `--apply`:

```text
python manage.py compose_hunter_class_basics --base-checksum 90e74e8d6096c07b212e015daf2e96c3caff1f2333cb8674d795f8fd2882edd2 --expected-checksum da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289
```

Somente depois de validar o resultado na copia, repetir com `--apply` nessa
copia e verificar personagens, recursos, magias, inventario e subclasses.
O comando recusa checksum divergente; nao ajustar o esperado para contornar
uma divergencia sem revisar a causa. O estado final usa:

```text
HUNTER_CREATOR_RULESET_CHECKSUM=da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289
```

6. Validar fluxos novos e personagens legados, inclusive multiclasse. Ordens
   antigas e novas nao sao unificadas por nome. Nao converter fichas antigas
   automaticamente. Conferir a sequencia em `POSTGRESQL.md` e registrar hashes
   dos artefatos efetivamente ensaiados.
7. Repetir somente a sequencia aprovada no alvo autorizado, sem escritas
   concorrentes que invalidem o ensaio. Registrar migracoes, insercoes,
   checksum ativado e smoke. O push do codigo NAO executa esta sequencia.

## Recuperacao por falha

Para recuperar integralmente um banco perdido, preferir o dump PostgreSQL
fresco restaurado num banco vazio separado; validar e trocar a conexao de
forma coordenada. Restaurar um backup antigo depois de novas escritas perde
essas escritas: interromper e reconciliar antes, nao sobrescrever.

Se so existir o JSON do admin, ele precisa ser ensaiado em banco vazio com
schema compativel, referencias auth/contenttypes e sequencias verificadas.
Nao confundir esse processo de desastre com a instalacao aditiva do rework.

## Limite desta entrega

Este guia corrige a ordem das instrucoes existentes. Nao aplica dados, nao
certifica o estado atual da producao e nao substitui o preflight fresco.
As fixtures privadas nao sao publicadas no repositorio.
