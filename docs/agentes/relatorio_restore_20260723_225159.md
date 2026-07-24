# Restore de conteudo prod (dev-vence) - 2026-07-23 22:51:59

- **Arquivo:** `ref/backups/restore_consolidado_20260723_225159.json`
- **Relatorio de maquina:** `ref/backups/restore_consolidado_20260723_225159.report.json`
- **SHA-256:** `c85a8a8055f2dbed38f3e9e97a15672931e3a5fce7454393d7f6d71697fbc590`
- **Registros:** 5.011, em 21 modelos com dados.
- **Baseline:** `ref/backups/restore_consolidado_20260722_202656.json`
- **Rollback:** `ref/backup_completo_20260722_230533.json`

Os arquivos JSON ficam somente no disco em `ref/backups/` e nao devem ser
commitados. Este Markdown e o registro versionado da rodada.

## Mudanca de conteudo

A unica tabela diferente do baseline e `home.tbitemmagico`:

- 266 itens alterados;
- 0 inseridos;
- 0 removidos;
- unico campo alterado: `slot`;
- contagem preservada em 953 itens magicos.

A auditoria cobriu 329 itens maravilhosos/focos/instrumentos que estavam no slot
generico `empunhado`. Foram aplicadas as decisoes de confianca alta ou media:

- 266 slots efetivamente corrigidos;
- 43 itens ja estavam no slot proposto;
- 20 casos de baixa confianca ficaram em `hold` e nao foram alterados.

Exemplos corrigidos: `apito-da-aguia` virou `item_menor`; recipientes e objetos de
ativacao pontual passaram para `objeto`; acessorios vestiveis foram encaminhados
para seus slots corporais. O log completo antes/depois esta em
`scratch/equipaveis_aplicacao_log.json`.

## Seguranca

O fixture foi gerado por `manage.py export_restore_consolidado` com:

- serializacao UTF-8, sem BOM, `indent=2` e CRLF puro;
- mundo/mapa fora do arquivo, portanto preservados na producao;
- nenhum modelo de memoria no fixture;
- `deserialize` completo dos 5.011 registros;
- simulacao de `sincronizar_conteudo` em transacao revertida;
- `merge_mem_ok=true`;
- hash independente dos bytes em disco igual ao report.

O motor da ficha ja ignora `equipado=True` para item magico que deixou de ser
equipavel. Isso preserva as linhas de inventario antigas sem conceder mecanica
indevida e sem apagar dados de personagem.

Validacoes executadas:

- `manage.py test home --parallel 4`: 323 testes, todos aprovados;
- `manage.py validate_tags`: `ERROR=0`, `WARN=0`;
- `manage.py check`: sem problemas;
- `node --check` em `subir_nivel.js` e `markdown.js`;
- regressao especifica Paladino 6 / Feiticeiro 2 para subclasse e magias.

## Codigo desta rodada

O restore nao carrega mudancas de codigo. O deploy do codigo deve ocorrer antes
do merge e inclui:

- level-up de multiclasse com contexto explicito da classe para subclasse,
  truques, magias conhecidas e troca de magia;
- cotas de magia contabilizadas por classe, sem Paladino preencher a cota de
  Feiticeiro;
- correcao do `::toggle` do Markdown que exibia o HTML da Manifestacao Mistica
  como bloco de codigo;
- mutacoes da edicao de ficha via fetch, mantendo fallback PRG;
- comando auditavel de equipabilidade e gerador reproduzivel do consolidado.

## Aplicacao

1. Atualize o codigo e rode as migracoes.
2. Baixe um backup completo fresco da producao.
3. No console, use **Merge de conteudo (dev -> producao)**.
4. Envie `restore_consolidado_20260723_225159.json`.
5. Confirme no relatorio da tela que a memoria permaneceu intacta e que
   mundo/mapa foram preservados por ausencia.

Nao use a restauracao cega por PK para este fixture: os PKs de dev e producao
podem divergir. O fluxo correto e o merge por slug.
