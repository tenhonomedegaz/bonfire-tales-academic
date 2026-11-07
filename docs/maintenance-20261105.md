# Checkout, contas e cadastro de mestres

## Entrega

- Checkout: nao enviar customerData incompleto ao Asaas; os dados fiscais sao
  preenchidos na pagina hospedada. O beneficiario continua fixado no pedido local.
  Nome do item limitado a 30 caracteres. Sandbox usa seu proprio host de checkout.
- Planos: seletor explicito de 1/3/6/12 meses, total do periodo e modalidade.
  Somente o mensal possui recorrencia; periodos maiores sao pagamentos unicos.
- Bot: links assinados conferidos para cada periodo; rotulos de desconto ajustados
  para 10/15/25%, sem prometer meses gratis inexistentes. Precos inalterados.
- Contas: indice unico para LOWER(TRIM(email)), exceto enderecos vazios de contas
  legadas. Novos cadastros exigem email. Cadastro, perfil, admin e concorrencia
  possuem protecoes contra duplicidade.
- Formulario: seis perguntas da referencia, respostas privadas com copia da
  versao das perguntas, limite de tres tematicas e campo Outro. Permanece fechado.
- Vitrine: identidades oficiais por numero, independentemente de existir login.
  Portfolio proprio em /mestre/fogueiras/NUMERO/, perfil pessoal somente quando
  vinculado. Apresentacoes privadas e respostas de candidatura nao sao publicadas.
- Historico: planilha e bot, quantidade de aventuras e total conhecido. Recibos
  de republicacao impedem contagem dupla. Quantidades legadas ausentes ficam
  A confirmar; nunca sao calculadas a partir de MM.

## Limpeza de contas

Migration 0171 faz backup no servidor antes de limpar duplicados. O preflight
confere todos os grupos antes da primeira exclusao e bloqueia contas e perfis.
Remove apenas contas vazias: nao transfere nem recria PKs de personagens,
compras, historicos, carteiras ou vinculos Discord. Se houver dados em mais
de uma conta do grupo, interrompe e reverte sem escolher arbitrariamente.
Mantem recibos UserAccountMergeReceipt e preserva a confirmacao do mesmo email.
A migration de limpeza e irreversivel sem restaurar backup.

Se 0171 falhar com "pending trigger events" ao criar o indice no PostgreSQL,
atualizar o codigo e executar /site-update novamente. O helper agora executa
SET CONSTRAINTS ALL IMMEDIATE antes do CREATE INDEX, validando as FKs pendentes
sem separar a limpeza e o indice em transacoes. A migration continua atomica:
uma falha reverte suas alteracoes; nao usar --fake nem apagar migrations.
Teste de regressao cobre a ordem dos comandos PostgreSQL com executor simulado;
nao substitui a conferencia da execucao real apos o deploy.

Simulacao do backup de producao: 101 contas, 11 grupos repetidos, 14 logins
vazios removiveis, 87 contas restantes. Arquivo original e recibos de simulacao
guardados fora do Git em LOCALAPPDATA/BonfireQA/account-checkout-audit-20261105,
com acesso restrito ao usuario e SYSTEM. Nenhuma senha ou hash consta neste guia.

## Ativacao e conferencia

Executar /site-update para instalar codigo e migrations 0170/0171.
Depois consultar a operacao account-email-audit (read, chave superuser):
contagem de duplicados, indice unico, recibos e hash dos PKs/donos de personagens.
Gerar apenas checkout de teste nao pago; nao executar cobranca real.

Importar uma unica vez o pacote mercado-mestres-20261105-roster-addendum via API
existente: inclui apenas F76 - Mestre Casper, ausente da copia antiga.
Nao reimportar F01-F74. Saldo de fonte reservado, sem conta nem credito novo.
Reservar o Discord confirmado do Casper pela operacao master-legacy-confirm.
F75 permanece vazia. Esse complemento nao reabre solicitacoes.

## Evidencias

- home/test_master_legacy.py --isolated: 54 testes.
- home/test_maintenance_batch.py --isolated --production-backup --migration-check:
  checkout, webhook, formulario, portfolio, duplicatas e simulacao isolada.
- Bot: subscriptionCheckoutPeriods.spec.ts e activeColabSubscription.spec.ts:
  tres testes, sem chamadas de pagamento.
- docs/qa/maintenance-20261105/ui-verification.json: navegador desktop/mobile,
  plano trimestral correto, pagamento interceptado localmente, sem cobranca.
- Capturas locais na mesma pasta. Nenhum dado pessoal ou segredo nesses testes.

Referencias oficiais: https://docs.asaas.com/docs/como-informar-os-dados-do-cliente
e https://docs.asaas.com/reference/criar-novo-checkout.

## Vitrine e entrada de mestres

O menu Mestre inclui Vitrine de mestres em desktop e mobile. A paginacao tem
botoes, limites desabilitados, pagina atual e ancora no inicio dos resultados.
Historicos priorizam um original do bot sobre o placeholder importado quando
ha um unico par de titulo normalizado no escopo do mesmo mestre, mesmo com datas
de relato diferentes (inicio, termino, publicacao ou resgate). Titulos repetidos
exigem correspondencia de data unica em ambos os lados; casos ambiguos continuam
separados, sem escolher por proximidade. A data exibida usa a missao original.
Isso nao emite moedas nem altera o bot. Sem quantidade comprovada, exibe
Nao registrada; a conclusao importada aparece como Concluida (planilha).

Identidades oficiais com Discord reservado sao reivindicadas no callback OAuth
(novo cadastro, login Discord ou vinculo a conta existente). O perfil de mestre
e aprovado automaticamente, mesmo com solicitacoes fechadas, sem reaplicar
carteira ja importada. Suspensao/recusa explicita e conta ja vinculada a outro
dono continuam protegidas. Informar um ID em texto nao prova posse do Discord.
F17/Kitsu foi reservado via API apos confirmacao do usuario nesta conversa.
