# Checkout avulso de cosméticos

## Configuração

No admin, cadastre um cosmético no catálogo existente e crie sua `CosmeticCheckoutOffer` com preço em reais. A oferta começa inativa. Ative-a apenas depois de definir o valor comercial e confirmar a configuração do Asaas. Não há preço padrão nem criação remota de checkout ao salvar a oferta.

## Fluxo

`/cosmeticos/checkout/` exige login. O POST aceita somente o slug de uma oferta ativa; o servidor congela usuário, cosmético, nome e valor em `AsaasCheckoutOrder` e `CosmeticCheckoutPurchase`. A referência externa continua `bonfire_order:<uuid>`. O adaptador Asaas existente cria um checkout avulso. Repetir o POST durante 65 minutos retorna o pedido existente, ultrapassando a expiração remota de 60 minutos. Se a primeira chamada der timeout, o mesmo pedido permanece pendente sem prazo automático de nova tentativa; a tela mostra conciliação pendente e não tenta outra cobrança.

O webhook existente valida o token antes de ler dados. Para compras de cosmético, consulta o pagamento pela API e só aceita referência, identificador, status liquidado e valor completos. O evento autenticado registra ID de evento e pagamento; pagamento confirmado concede o item de forma transacional e idempotente. Valor divergente bloqueia concessão e exige conciliação manual. Eventos não liquidados são ignorados. O status local `/cosmeticos/checkout/<uuid>/` é visível somente ao beneficiário e não consulta a API financeira.

`home.cosmetic_entitlements.has_permanent_cosmetic(user, cosmetico)` é o contrato de leitura do direito permanente. Os seletores, títulos, insígnias e renderer do perfil reconhecem uma compra confirmada mesmo se uma origem temporária suspender a linha única de `TbUsuarioCosmetico`; itens inativos continuam indisponíveis. A integração do bot/Colab ainda deve consultar esse contrato antes de negar posse ou revogar a concessão. Ofertas avulsas não usam moedas sociais.

## Operação

Aplicar a migração `0143` no processo normal de implantação antes de ativar ofertas. Não há migração de dados antigos. Testes locais usam mocks da API e banco PostgreSQL isolado; nenhum checkout financeiro real é criado.
