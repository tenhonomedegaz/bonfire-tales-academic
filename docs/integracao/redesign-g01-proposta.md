# G01 — proposta estrutural do redesign Bonfire

## Decisão do PO em 17/10/2026

- **A:** sem aprovação integral. A `0152` da fonte cria calendário, visita e estoque; estrutura da caravana continua pendente. A `0153` altera três itens por slug e não está autorizada. Tags e dados devem usar o fluxo genérico existente, mediante decisão específica sobre esses itens.
- **B:** aprovado apenas em DEV isolado. Reconciliar com a implementação em `../bonfire-bot-main`: cargo de Mestre/Mestre em Teste e propriedade da missão continuam sob política do bot; perfil, moderação e anúncio no site não devem conceder cargo ou modificar missões do bot.
- **C:** adaptar direitos e marcos já existentes. A compra de slot por 5.000 MM substitui o antigo Mestre Ouro como assinatura; marcos 5, 9 e 13 explicitados pelo PO, demais marcos exigem conferência. Não cobrar retroativamente nem duplicar direitos.

Para o resgate de 5.000 MM, a branch reutiliza `MestreOuroDireito`, a trava de conta, a carteira e `TbTransacaoMestre` já existentes. A rota de slots registra `tipo=resgate` uma única vez, sem reativar a oferta de `assinatura` nem iniciar pagamento em reais. Direito prévio retorna sem débito; compras ou mensalidades legadas sem direito comprovado exigem reconciliação antes de novo resgate. Esta parte não requer `TbSlotDireito` nem migration nova. Os marcos de nível e os demais efeitos propostos na `0157` da fonte continuam pendentes de conferência e reconciliação, inclusive o nível 20; o texto histórico abaixo não os torna autorizados.

`manage.py preview_redesign_c` consulta, em PostgreSQL e transação somente leitura, candidatos com personagem nos níveis 5, 9, 13 e 20, marcos sustentados por eventos e revisões existentes, direito vitalício, histórico legado e resgate MM órfão. Também lista as conquistas de nível configuradas para esses marcos, seus cosméticos e concessões ativas. Esses registros não demonstram política de tokens ou slot por nível. O resultado inclui a identidade da conexão e IDs de conta para reconciliação; não concede slot ou token. Na consulta somente leitura da base principal em 17/10/2026, havia zero candidatos e zero conquistas de nível configuradas; as contagens não validam a preservação de dados no DEV dedicado. A `0157` da fonte semeia automaticamente direitos nos níveis 13 **e 20**, mas o PO confirmou o slot do nível 13 e deixou os demais marcos para conferência. Nenhum desses candidatos ativa concessão automática nesta branch.

- **D:** aprovado apenas em DEV isolado, inclusive o conceito da `0158`; adaptar a migration ao histórico real. Antes de tocar o banco, inventariar registros afetados e preparar reversão de dados. Preservar direitos adquiridos, recibos, saldo e personagens. Oferta demonstrativa não cobra.

O inventário pré-mudança de D deve ser exportado antes de `0155_redesign_theme_pilot`, no head `0154_redesign_master_portfolio`, com `manage.py preview_redesign_d --expected-home-head 0154_redesign_master_portfolio --output <arquivo_absoluto_fora_do_repositorio.json>`. O comando exige PostgreSQL, verifica o head informado, lê em transação consistente e imprime contagens e SHA-256; o JSON guarda os valores originais de recompensas de assinatura, temas, ofertas, posses, recibos, direitos e carteira MM, além da identidade da conexão (engine, nome, host, porta e usuário). As ofertas são lidas pelas colunas existentes em `0154`; `demonstration` só surge em `0155`. Os comandos de reconciliação recusam snapshots de outra conexão, mesmo que o nome do banco coincida. Esta exportação não altera dados nem substitui a operação compensatória e a reversão específica a preparar antes de aplicar D em DEV isolado.

Para a desativação das recompensas legadas de `assinatura`, `manage.py reconcile_redesign_d_rewards --snapshot <arquivo> --sha256 <hash>` mostra os IDs afetados. `--action retire --confirm G01-D-REWARDS` desativa apenas os registros do inventário; `--action restore --confirm G01-D-REWARDS` restaura somente o estado `ativo` original. O comando exige o mesmo banco PostgreSQL, compara todos os demais campos e aborta se o catálogo divergiu. Não modifica direitos, recibos, transações ou saldos. As ofertas de temas são fechadas pelo rollback do piloto; resgates MM já realizados exigem decisão de estorno por recibo, com a operação compensatória existente.

Para reverter **o piloto atual** em uma transação, `manage.py rollback_redesign_d_pilot --snapshot <arquivo> --sha256 <hash> --confirm G01-D-ROLLBACK-PILOT` fecha as ofertas piloto, arquiva temas sem uso, mantém ativos os temas adquiridos e restaura as recompensas de assinatura ao estado inventariado. Qualquer divergência aborta as duas operações. O resultado separa `archived_slugs` de `retained_owned_slugs`. Direitos, recibos, saldo e transações MM permanecem; eventual estorno usa a operação compensatória auditável por recibo, separada do fechamento do catálogo.

Na branch de integração, `0155_redesign_theme_pilot` adiciona somente o indicador `demonstration` à oferta atual, com padrão falso; não executa o `RunPython` da `0158` da fonte. Depois do inventário pré-D, `manage.py reconcile_redesign_d_pilot --snapshot <arquivo> --sha256 <hash>` mostra os três slugs novos do piloto fixado. `--action seed --confirm G01-D-PILOT` cria apenas temas ausentes e ofertas demonstrativas; `--action archive --confirm G01-D-PILOT` fecha as ofertas, arquiva temas sem uso e preserva o catálogo de temas já adquiridos para equipagem. Colisões com temas já presentes exigem reconciliação manual. A oferta demonstrativa não debita MM nem abre cobrança Asaas. Ofertas MM futuras exigem configuração não demonstrativa e usam recibo e ledger com estorno próprio; o checkout em reais exclui as três sementes do piloto mesmo se o indicador demonstrativo for alterado. Cosméticos anteriores com slug coincidente, mas sem a marca do piloto, preservam o fluxo existente.

A rota privada `colaborador/assinatura/` lê o plano e o histórico das tabelas existentes do bot via e-mail verificado ou Discord vinculado. Falha de consulta aparece como estado desconhecido, sem sugerir cancelamento nem conceder benefícios. A página não cria checkout, cancela assinatura ou modifica direitos; os links de fichas levam à lista existente de personagens.
- **E:** somente adaptações necessárias a B/D, mantendo API, autenticação, CSRF e configuração atuais.
- **F:** adiado; sem importação de regras, fixtures ou mecânicas.

As migrations da fonte são uma cadeia, não uma autorização por dependência. B/D devem partir da `0151` real em migrations próprias e não aplicar A/F implicitamente, usar `--fake` ou editar migrations já aplicadas. G00 e G02 permanecem. A produção atualizada com o último commit enviado ainda não inclui automaticamente este redesign.

Na branch isolada, `0152_redesign_master_participation` e `0153_redesign_master_announcements` são migrations **locais do lote B**. Seus números não autorizam nem executam `0152_magic_market_caravan` ou `0153_fate_deck_server_attunement` da fonte. O anúncio no site é uma vitrine moderada; missões, fila e cargo no Discord continuam no bot. A migration local `0156_redesign_master_commercial` adiciona verificação independente de aventuras já registradas e autorização comercial; ela depende apenas de `0154_redesign_master_portfolio`, enquanto `0157_merge_redesign_b_d` reúne as branches B e D sem operação de dados. Três mesas verificadas nos últimos 30 dias, incluindo uma aberta, e autorização administrativa vigente permitem enviar anúncios pagos ilustrativos à revisão. A central de mestres permite a revisão por equipe com a permissão existente `autorizar_mestres`; nenhum desses registros cria missão, crédito MM ou cobrança.
`0154_redesign_master_portfolio` também é local do lote B: cria somente a galeria moderada de trabalhos, sem executar a cadeia de migrations da fonte. Publicação requer revisão separada e mestre autorizado; uma edição retira o trabalho da vitrine até nova revisão. Nenhum arquivo anterior é apagado na substituição de imagem.

## Proposta original (histórico)

O texto abaixo registra a proposta anterior; a decisão do PO acima prevalece. A proposta solicitava, por lotes independentes, a implementação serial de backend que o pacote
fixado em `7289711136e340afe5a13ba397ecce978071896d` requer. Esta proposta foi
conferida contra a base limpa `f3e34469cc00306131af9511b758d5e050cad769` e o
manifesto S01: são 506 caminhos G01 (451 de Python/estrutura, 41 de conteúdo
mecânico e 14 de revisão), com 22 rotas novas. Não há aplicação aprovada por este
documento, inclusive de migrations, dados ou segredos.

As migrations `0152` a `0160` da fonte formam uma cadeia única a partir de `0151`; essa cadeia não será executada em bloco. Novas migrations aprovadas serão reconciliadas sobre a `0151` real e aplicadas somente em DEV isolado após inventário e reversão adequados. PKs existentes,
usuários, fichas, compras, uploads e escolhas legadas permanecem a fonte de
verdade. Não copiar `.env`, dumps, contas ou chaves da fonte.

## Lote G01-A — caravana e catálogo mágico

**Dependência adicional verificada em 17/10.** Os templates
`home/templates/home/partials/market_consultation_cards.html` e
`market_item_notes.html` carregam `home/templatetags/distance_display.py` e o
filtro `dual_distance`. A base atual não registra essa biblioteca; compilar
esses dois templates falha com `TemplateSyntaxError`. A implementação do
filtro depende também de `home/distance_presentation.py` e
`home/rules_terminology.py`. Incluir esses três arquivos Python no lote G01-A
para revisão explícita antes de ativar a consulta de mercado. Até lá, o
mercado existente continua acessível; a consulta nova fica sem integração.

O template completo `itens_mundanos_content.html` também carrega
`home/templatetags/market_display.py` (`copper_price`, `market_symbol`,
`market_lookup` e `mastery_labels`). A base atual não tem essa biblioteca.
`home/mundane_market_reference.py`, já incluído neste lote, fornece as linhas
`guide-sobre`/`guide-economia` e o mapa `market_legacy_navigation`; sem ele,
os dois botões de guia do cabeçalho não têm destino. Aprovar explicitamente a
biblioteca e a ligação dessas linhas ao contexto antes de ativar o template
completo. Não substituir preços ou guias por valores inventados no frontend.

**Arquivos.** `home/migrations/0152_magic_market_caravan.py`,
`home/migrations/0153_fate_deck_server_attunement.py`, `home/models.py`,
`home/magic_market.py`, `home/magic_market_views.py`,
`home/magic_market_classification.py`, `home/mundane_market_reference.py`,
`home/templatetags/market_display.py`,
`home/templatetags/distance_display.py`, `home/distance_presentation.py`,
`home/rules_terminology.py`,
`home/urls.py`, `home/views.py`, `home/data/mundane-market-reference.txt`,
`home/data/itens_magicos_nomes_ingles.csv`,
`home/data/magias_nomes_ingles.csv` e `scripts/audit_magic_market_shops.py`.

**Motivo.** Disponibiliza a caravana/estoque de itens mágicos, inclusive a tela de
configuração e a compra de pergaminho. A `0152` cria `MagicMarketCalendar`,
`MagicMarketVisit` e `MagicMarketStock`; este último usa FKs protegidas para
`TbItemMagico` e visita, com unicidade `(visit, item)`.

**Impacto em PK/FK/dados.** Só introduz PKs `BigAutoField`; não renomeia PK/FK
legado. A operação de estoque passa a depender de itens existentes e uma visita
não pode ser apagada enquanto houver estoque. A `0153` merece aprovação separada:
ela modifica, por slug, exatamente três linhas de `TbItemMagico`, remove as tags
`requires:por_clerigo_ou_paladino` e `consumable` e substitui a sintonização por
“Por qualquer classe”. O `backwards` recompõe esses valores apenas se a descrição
ainda for exatamente essa, portanto não é restauração confiável depois de edição
manual.

**Riscos.** Estoque concorrente, preço/loja divergente do catálogo corrente e
mudança mecânica de sintonização em itens ativos. A seleção por slug em 0153 pode
não alcançar catálogo já divergente.

**Reversão.** Desabilitar as rotas e reverter o código preserva os registros. Para
0152, remover tabelas só depois de exportar registros. Para 0153, aplicar uma
correção auditada por PK/slug e backup dos três registros; não tratar o
`backwards` automático como reversão de produção.

**Alternativa frontend.** Exibir catálogo e calendário apenas como vitrine, com
botões desabilitados/explicação de disponibilidade; conservar a compra existente
sem a caravana.

## Lote G01-B — mestres, anúncios, portfólio e as 15 rotas de participação

**Arquivos.** `home/migrations/0154_tbperfilmestre_tbmesaanuncio.py`,
`0155_master_authorization_portfolio_mission.py`,
`0159_master_portfolio.py`, `0160_table_offers.py`, `home/models.py`,
`home/master_hub.py`, `home/master_views.py`, `home/master_portfolio.py`,
`home/portfolio_views.py`, `home/master_commercial_admin.py`,
`home/table_commerce.py`, `home/permissions.py`, `home/admin.py`, `home/urls.py`
e `home/views.py`.

**Motivo.** Formaliza perfil de participação, autorização de mestre, anúncios de
mesa, galeria moderada e vitrine de mesas. Inclui estas 15 rotas novas:

| Rota | Nome |
| --- | --- |
| `mestre/portfolio/` | `master_gallery` |
| `mestre/portfolio/novo/` | `master_work_create` |
| `mestre/portfolio/revisao/` | `master_gallery_review` |
| `mestre/portfolio/<int:pk>/editar/` | `master_work_edit` |
| `mestre/portfolio/<int:pk>/revisar/` | `master_work_review` |
| `mestre/portfolio/<int:pk>/` | `master_work_detail` |
| `mestre/central/` | `master_dashboard` |
| `mestre/participacao/` | `participation_edit` |
| `mestre/solicitar/` | `master_request` |
| `mestre/autorizacoes/<int:pk>/` | `master_authorize` |
| `mestre/mestres/` | `masters_directory` |
| `mestre/mesas/nova/` | `master_table_create` |
| `mestre/mesas/<int:pk>/editar/`, `/acao/` e `/` | `master_table_edit`, `master_table_action`, `master_table_detail` |

**Impacto em PK/FK/dados.** 0154 cria `TbPerfilMestre` com `OneToOne` de usuário,
`TbMesaAnuncio` com FKs para mestre/revisor e índice `(estado, data)`. 0155 adiciona
status de autorização, auditoria e campos JSON de seleção à mesa. 0159 cria
portfólio, verificação de mesa e autorização de vitrine, com FKs `PROTECT` em
relações comerciais. 0160 altera `data` para nula e introduz preço, modalidade,
condições e marca demonstrativa. Não há migração de aprovações autodeclaradas:
perfis existentes começam sem aprovação.

**Riscos.** Escalonamento por permissão, publicação indevida, upload/URL remoto
não confiável, exposição de contato e anúncio de mesa paga que pareça contratação
real. `data` nula exige que listagens e ordenações suportem agenda “a combinar”.

**Reversão.** Retirar as rotas e despublicar itens/anúncios preserva dados. Antes
de remover tabelas/campos, exportar portfólios, decisões e anúncios. Mudanças de
estado devem ter trilha de auditoria; não apagar autorização para simular reversão.

**Alternativa frontend.** Manter páginas de mestre, portfólio e mesas como
apresentação estática ou links para fluxos existentes, sem formulário, moderação
ou preço acionável.

## Lote G01-C — fichas, slots, lenda e limites de conta

**Arquivos.** `home/migrations/0156_tbfeitolenda.py`,
`0157_character_slot_rights.py`, `home/models.py`, `home/character_slots.py`,
`home/slot_views.py`, `home/slots.py`, `home/permissions.py`,
`home/legend_views.py`, `home/character_engine.py`, `home/views.py`,
`home/urls.py`, `home/admin.py`, `home/ranks.py`,
`home/templatetags/rank_icons.py` e
`home/templatetags/background_icons.py`.

**Motivo.** Sustenta a página pública de Lenda e a política de capacidade de
personagens. Rotas novas: `personagens/<int:pk>/lenda/` (`personagem_lenda`) e
`jogador/personagens/slots/` (`character_slots`).
Os templates completos de fichas, perfis, missões e antecedentes carregam
`rank_icons` ou `background_icons`; `rank_icons` depende de `home/ranks.py`.
Essas bibliotecas ausentes precisam de revisão G01 antes de reativar as
apresentações correspondentes.

**Impacto em PK/FK/dados.** 0156 cria `TbFeitoLenda` com FK em cascata para
`TbPersonagem`. 0157 cria `TbSlotDireito`: FK `PROTECT` para usuário, pedido Asaas
e transação MM; unicidade por `(user, chave)` e por marco de nível 13/20. Também
indexa `TbPersonagem.arquivado` e semeia direitos para donos que já tenham
personagem nos níveis 13 ou 20, sem alterar fichas. Compra MM debita 5.000 MM e
registra ledger, devendo ser idempotente por chave de requisição.

**Riscos.** Travar criação/operação de fichas legadas, concessão duplicada em
reexecução manual, concorrência de saldo e acesso público a feitos não publicados.

**Reversão.** Suspender aplicação das regras de capacidade antes de mexer nos
direitos; revogar concessões de compra com lançamento compensatório auditável,
nunca apagando transação. Para o backfill de nível, registrar a lista de usuários
afetados antes de executar.

**Alternativa frontend.** Mostrar a contagem atual como informativa e continuar
a usar o limite existente; exibir Lenda somente quando a página puder ler os
dados já existentes.

## Lote G01-D — temas, assinatura e economia

**Arquivos.** `home/migrations/0158_theme_studio_pilot.py`, `home/models.py`,
`home/theme_studio.py`, `home/theme_collections.py`, `home/cosmetic_entitlements.py`,
`home/cosmetic_packages.py`, `home/cosmetics.py`, `home/event_cosmetics.py`,
`home/subscriptions.py`, `home/subscription_views.py`, `home/urls.py`,
`home/views.py`, `home/permissions.py`,
`home/templatetags/commerce_presentation.py`, `home/static/cosmetics/*.json` e
`home/static/brand/*.txt`.

**Motivo.** Introduz o ateliê e resgate de tema por MM, além da página de
assinatura. Rotas novas: `atelie/` (`theme_studio`),
`atelie/adquirir-mm/` (`theme_acquire_mm`) e
`colaborador/assinatura/` (`subscription_management`).
As telas completas de checkout e loja de evento carregam
`commerce_presentation`, ausente na base. Sua aprovação neste lote cobre
somente apresentação de ofertas; não concede direitos nem autoriza cobrança.

**Impacto em PK/FK/dados.** A **0158 requer aceite individual**. Ela adiciona
`demonstration` em oferta de checkout, cria `CosmeticMMRedemption` com FKs
`PROTECT` para usuário/cosmético/transação e unicidade por requisição e por
propriedade. O `RunPython` cria ou reaproveita três temas e suas ofertas, e
desativa todas as recompensas de mestre do tipo `assinatura`. O reverso é
`RunPython.noop`: temas, ofertas e a desativação permanecem após rollback do
schema. Ofertas demonstrativas não podem cobrar nem debitar MM; a compra MM deve
travar perfil, validar saldo, registrar uma única transação e conceder somente
após êxito.

**Adaptação aprovada em DEV isolado.** A implementação local separa schema e
dados: `0155` introduz apenas o marcador de demonstração; `0158` cria o recibo
MM e `0159` guarda o estado anterior do inventário para estorno. A aquisição
`atelie/adquirir-mm/` usa a carteira e o ledger atuais, chave de idempotência e
oferta ativa não demonstrativa. O estorno `reverse_redesign_d_mm` registra crédito
compensatório, preserva o débito e recibo originais e restaura a posse anterior.
As sementes piloto continuam demonstrativas. O inventário pré-D no banco DEV
real continua obrigatório antes de migrar ou aplicar dados nesse ambiente.

**Riscos.** Débito duplicado, entrega de cosmético sem pagamento, reativação
indevida de benefício, confusão entre preço ilustrativo e cobrança real, e
incompatibilidade com checkout/Asaas existente.

**Reversão.** Desativar ofertas e rotas primeiro; reverter resgates por operação
compensatória e revogar entitlement conforme política, preservando recibos. Para
0158, preparar antes uma migração corretiva explícita que reative somente os
registros de assinatura identificados e remova/arquive apenas sementes sem uso;
não executar `migrate` para trás como plano de dados.

**Alternativa frontend.** Ateliê em modo prévia, sem POST de aquisição; assinatura
como página de estado/link do fluxo atual. Preços de mesas e temas ficam
explicitamente demonstrativos.

## Lote G01-E — contrato HTTP, configuração, segurança e permissões

**Arquivos.** `bonfire/settings.py`, `bonfire/settings_release_test.py`,
`bonfire/urls.py`, `bonfire/asgi.py`, `bonfire/wsgi.py`, `manage.py`,
`.env.example`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`,
`.gitattributes`, `home/apps.py`, `home/context_processors.py`, `home/signals.py`,
`home/db_access*.py`, `home/admin_navigation.py`, `home/admin.py`,
`home/permissions.py`, `home/urls.py`, `home/views.py` e os módulos Python novos
de apresentação/contrato listados no manifesto S01.

**Motivo.** Acopla as rotas aos módulos, registra apps/serviços e preserva os
contratos de autenticação, sessão, CSRF, estáticos e checkout. A fonte usa
operações atômicas e `select_for_update` nos fluxos de saldo, slots, anúncios e
resgates; as permissões novas de revisão/autorização são
`home.revisar_mesa_anuncio` e `home.autorizar_mestres` e exigem staff mais a
permissão correspondente.

**Impacto em PK/FK/dados.** Não cria dados por si só, mas muda a superfície HTTP,
validações e acesso. Configuração de banco, hosts, CSRF e Asaas precisa consumir
somente variáveis já provisionadas; valores secretos não entram em código, docs
ou commits.

**Riscos.** Regressão de login/CSRF, rota sem decorador adequado, permissões
herdadas incorretamente, exposição de webhook ou troca de dependência que altere
produção. As 22 rotas novas devem responder 404/403/405 conforme contrato e não
abrir uma ação sensível por GET.

**Reversão.** Feature flags/remoção de `urlpatterns` e restauração pontual de
configuração versionada; não remover variáveis no cofre. Cada endpoint entra com
teste de permissão, método e usuário anônimo antes de ser exposto.

**Alternativa frontend.** Navegação e cartões usam URLs existentes ou estado
indisponível; não criar endpoints fictícios nem links de POST.

## Lote G01-F — conteúdo mecânico, fixtures e contratos de publicação

**Arquivos.** Os 41 itens `content_or_mechanics` do manifesto, em especial
`home/fixtures/conteudo.json`, `home/fixtures/conteudo_manifest.json`,
`home/tag_library.json`, `home/rules/*.json`, `home/content_*.json`,
`home/content_packages/*.json`, `home/data/epic_talents.json`,
`home/data/traps_cineria.json`, `home/data/vastieren*.json`,
`home/data/vastieren/*.json`, `home/data/*nomes_ingles.csv`,
`deploy/restore_merge_tags_qa_20260801.json` e os JSON de prompts de
classes/subclasses/Vastieren.

**Motivo.** A fonte mistura apresentação com regras, tags, catálogos e possíveis
importações. O plano determina que mecânica permaneça em dados/tags genéricos e
que o redesign não autoriza troca silenciosa de conteúdo.

**Impacto em PK/FK/dados.** Fixtures podem criar, atualizar ou associar conteúdo
referenciado por fichas, classes, magias, itens e escolhas; os efeitos dependem do
importador e não devem ser inferidos do nome do arquivo. Nenhum PK/FK pode ser
substituído por carga de fixture. Cada arquivo precisa de diff semântico,
contagem antes/depois e chave natural/ID de destino definida antes de execução.

**Riscos.** Sobrescrever conteúdo local, quebrar tags interpretadas pelo motor,
apagar opções legadas, importar texto como regra e alterar fichas existentes.

**Reversão.** Snapshot lógico por tabela/chave natural e pacote de reversão
gerado no banco isolado; rollback só por patch de dados auditado. Não usar dump de
produção nem `flush` como reversão.

**Alternativa frontend.** Manter conteúdo atual e usar apenas estrutura visual;
cards sem dado novo devem indicar indisponibilidade, sem inventar regra ou
resultado.

## Ordem e condições de aceite

1. Aprovar ou recusar cada lote acima; aprovação de um não aprova outro.
2. Se A--D forem aceitos, implementar migrations serialmente, com backup lógico,
   plano de rollback e banco PostgreSQL isolado antes de qualquer ambiente
   compartilhado. 0153 e 0158 exigem aceite explícito no registro de mudança.
3. E entra junto do lote funcional correspondente, depois de revisão de métodos,
   autenticação, CSRF, permissão e segredo por referência de variável, sem valor.
4. F só entra após inventário semântico e aceite do responsável por regras.
5. Checkout/reserva/contrato de mesas pagas, relatórios de sessão, avaliações
   verificadas, disputas, repasses, compra de slots em reais e
   troca/cancelamento de assinatura continuam lacunas do pacote: nenhuma delas
   deve ser presumida como implementação deste G01.

## Evidência de inspeção

- Fonte: commit `7289711`; base: `f3e3446`; manifesto S01: 506 caminhos G01,
  22 rotas `source_only`, sem rota exclusiva da base.
- As migrations inspecionadas são exatamente `0152`--`0160` e dependem em cadeia
  de `0151_tbentregaeventoconquista`.
- Modelos vistos na fonte incluem `MagicMarket*`, `TbPerfilMestre`,
  `TbMesaAnuncio`, `TbFeitoLenda`, `TbSlotDireito`, `CosmeticMMRedemption`,
  `TbPortfolioMestreItem`, `TbVerificacaoMesa` e `TbAutorizacaoVitrine`.
- Não foram aplicadas migrations, importações, comandos de teste, alterações de
  configuração, arquivos de produto ou dados.
