# Cadastro numerado de mestres

## Politica atual

- Novas solicitacoes encerradas ate a revisao do formulario. O POST em
  `/mestre/solicitar/` retorna 403 sem criar perfil nem mudar pedidos existentes.
- `MASTER_APPLICATIONS_OPEN` vem desativado por padrao. Reabrir exige ativacao
  explicita; ocultar o botao nao e a protecao de acesso.
- Autorizar um perfil requer vinculo previo em `TbMestreLegado` com numero entre
  1 e `MASTER_ROSTER_MAX_NUMBER` (76 por padrao). Nomes de login diferentes do
  nome de mestre sao aceitos: a identidade possui FK para a conta.
- F75 esta vazia, confirmado pelo PO. Nao preencher por inferencia.
- F76 e Mestre Casper na planilha online de 05/11/2026; nao confundir com
  Caster F11. O pacote original importado contempla apenas F01-F74. Nao
  reimportar a planilha inteira nem resetar saldos para acrescentar identidades.

## Auditoria inicial de producao em 05/11/2026

17 perfis na fila completa: 16 aprovados e Borges pendente. Onze ja possuem
vinculo numerado; seis carecem de vinculo formal:

| Conta | Fogueira | Evidencia / proxima acao |
| --- | --- | --- |
| Schmidt | F65 - Mestre Ximit | Confirmacao explicita do PO nesta conversa. Vincular sem importar moedas. |
| Borges | F04 - Mestre Borges | Conferir Discord da conta com a autoria encontrada no bot antes de vincular. |
| Italo | F10 - Mestre Italo | Conferir Discord da conta antes de vincular. |
| Mark | F21 - Mestre Mark | Conferir Discord da conta antes de vincular. |
| Orin | F72 - Mestre Orin | Conferir Discord da conta antes de vincular. |
| Ogazzio | F73 - Mestre Ogazzio | Conferir Discord da conta antes de vincular. |

Os cinco nomes coincidem com o cadastro, mas nomes sozinhos nao comprovam a
propriedade de moedas. Nao criar novas Fogueiras, mesclar contas, suspender os
aprovados ou transferir saldo por aproximacao de nome. O pedido de Borges
pode ser de um mestre antigo; nao trata-lo como um novo mestre desconhecido.

## Resultado aplicado

Commit de codigo `5c9c497` publicado e instalado pelo `/site-update` confirmado
pelo PO. A auditoria posterior encontrou 17 perfis, todos com Fogueira valida,
sem solicitacoes pendentes ou perfis sem numero.

Os seis vinculos foram aplicados pela API com `wallet_mode: "defer"`:
Schmidt F65 (confirmacao do PO), Ogazzio F73 (Discord da conta igual ao autor
do bot) e Borges F04, Italo F10, Mark F21, Orin F72 (confirmados pelo PO).
O pedido de Borges foi resolvido como cadastro preexistente, nao como abertura
de nova Fogueira. Nenhuma carteira foi importada por essas seis operacoes.

Conferencia autenticada apos o deploy: aviso de solicitacoes encerradas
visivel, formulario de pedido ausente, envio direto retorna 403 e auditoria
inalterada antes/depois do teste. `applications_open` confirmado como falso
e limite vigente como 76. F75 permanece vazia. Nao houve nova importacao da
planilha online nem inclusao automatica de saldo de F76.

## API

`POST /api/db/v1/operations/master-registration-audit/`, escopo `read`, chave
criada por superusuario ativo. Payload: `{"offset":0,"limit":25}`; limite 50.
Retorna estado do cadastro, conta, Discord vinculado, versao e identidades
numeradas. Nao retorna e-mails, senhas, tokens nem dados financeiros.

Para corrigir vinculo confirmado, usar `master-legacy-bind` com o ID real da
identidade, login exato e `wallet_mode: "defer"`. Este modo vincula o cadastro
sem criar transacoes ou alterar a carteira; o saldo legado continua reservado
para conciliacao posterior. Repetir usa a mesma chave idempotente. Os modos
financeiros anteriores continuam disponiveis apenas para conciliacao explicita.

## Ativacao

Publicar o commit na dev e executar o `/site-update` habitual. Nenhuma nova
migration, segredo ou comando manual de banco e necessario. Apos o deploy,
consultar a auditoria pela API, conferir os vinculos e testar o bloqueio do
formulario com uma conta nao cadastrada. Nao criar pedido real so para testar.

Testes focados: `home/test_master_legacy.py --isolated`, incluindo bloqueio de
POST, reabertura explicita, autorizacao numerada, limite da Fogueira e vinculo
sem alteracao financeira.
