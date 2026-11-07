# Checkout Asaas vinculado a conta

## Identidades aceitas

O pedido (`AsaasCheckoutOrder`) preserva separadamente a conta do site, o Discord e o
e-mail. Pelo menos uma dessas identidades e obrigatoria.

| Origem | Vinculo inicial | Entrega |
| --- | --- | --- |
| Discord sem conta no site | Link assinado pelo bot | Imediata apos o webhook obter o e-mail da cobranca |
| Site somente com e-mail | Usuario + e-mail | Fica vinculada ao usuario; beneficios do Discord sao conciliados ao conecta-lo |
| Site somente com Discord | Usuario + Discord | Imediata apos o webhook obter o e-mail da cobranca |
| Site com ambos | Usuario + Discord + e-mail | Imediata |

O e-mail solicitado pelo Asaas e dado de cobranca. Nos links do bot, o destinatario do
produto e o Discord assinado no link e nao um e-mail digitado depois.

## Configuracao

Site e bot precisam ter o mesmo valor aleatorio e secreto:

```env
BONFIRE_CHECKOUT_SIGNING_SECRET=<mesmo-segredo-nos-dois-servicos>
```

O bot tambem usa:

```env
BONFIRE_SITE_URL=https://bonfiretales.com.br
```

O site continua exigindo `ASAAS_API_KEY`, `ASAAS_API_BASE` e `ASAAS_WEBHOOK_TOKEN`.
Nunca versionar os valores reais.

## Publicacao

1. Publicar as migrations `0095_asaas_checkout_orders` e `0096_asaas_partial_identities`.
2. Configurar o segredo igual no site e no bot.
3. Publicar o site e depois reiniciar/publicar o bot.
4. Confirmar no Asaas que o webhook aponta para `/webhooks/asaas/` e envia o token configurado.
5. Fazer uma compra de baixo valor em sandbox e conferir pedido, transacao e entrega.

O webhook e idempotente pelo ID do pagamento. Valor divergente nao concede beneficio.
Falha temporaria ao obter a identidade retorna erro retentavel para o Asaas reenviar.
