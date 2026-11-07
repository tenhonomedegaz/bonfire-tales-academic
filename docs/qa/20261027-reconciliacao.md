# Reconciliacao P0: perfil, cosmeticos e lojas

Este documento preserva a fotografia do levantamento P0. A integracao posterior
das etapas autorizadas e seu estado de publicacao estao em
`20261027-entrega-1-3.md`; a tabela final abaixo nao substitui esse aceite.

Data: 27/10/2026. Escopo: **somente levantamento/reconciliacao da etapa P0** do
plano `docs/planos/20261026-perfil-cosmeticos-lojas.md:80`.
Repositorio: `[local-path] Bonfas/BonfireSite-redesign-integration`.

## 1. Resultado e limites

**Levantamento entregue; igualdade entre ambientes NAO comprovada.**
Fixture = 24 cosmeticos; PostgreSQL local configurado = 30 ativos;
producao = 49 ativos, conforme leitura autenticada do Main descrita em E4.
Nao interpretar esses tres conjuntos como replicas identicas.

- As tres molduras legadas NAO foram deletadas do catalogo de producao.
  Estao ativas, livres e em ambos os escopos, com PKs 10, 11 e 12.
- Os oito slugs das tres luas/Vigilia estao AUSENTES dos catalogos local
  consultado e de producao. No repositorio sao rascunhos inativos.
  Seus manifests publicos respondem 200: publicar arquivo NAO cadastra cosmetico.
- A demo antiga NAO representava o estado/obtencao real: segundo E6/Main,
  o helper sintetico omitia as molduras basais e injetava os oito drafts como
  ativos/livres. Isso explica a previa sem as legadas e com luas liberadas,
  sem significar exclusao/concessao em producao ou aplicacao autorizada la.
- Producao: zero ofertas em reais e duas ofertas beta de evento gratuitas.
  Isto NAO autoriza ativar novas vendas ou inferir ofertas das luas/Vigilia.
- Os 24 assets CSS/JS/manifests amostrados responderam 200. Quatro sao
  identicos byte a byte e vinte diferem apenas em quebras de linha.
  **Nenhuma divergencia de conteudo normalizado foi observada nessa amostra.**
  Isto NAO identifica o SHA implantado nem prova execucao da previa autenticada.
- Por este agente, nao foram feitas alteracoes funcionais, migrations, imports/seeds, POSTs,
  concessoes, ativacao comercial, commit/push ou SQL em producao.
  Artes/animacoes de rank e restauracao Arcane (P4) ficaram fora do escopo.
- Unicos arquivos desta entrega: este documento e
  `docs/qa/tools/reconcile_readonly.py`. Mudancas concorrentes foram preservadas.

## 2. Registro de evidencias

| ID | Origem e momento | Alcance |
| --- | --- | --- |
| E1 | Git local + `git ls-remote origin refs/heads/dev refs/heads/main refs/heads/master`, 2026-10-27T15:59:09.467776+00:00 | SHA local, refs em cache e refs remotas lidas ao vivo; sem fetch/checkout |
| E2 | Arquivos de fixtures, migrations, draft e manifests lidos pelo coletor | Existencia/conteudo local; NAO estado do banco |
| E3 | PostgreSQL em loopback, DB configurado `postgres`, 27/10; credencial existente de `BonfireSite-main/.env`, nunca impressa | SELECT de catalogo e migrations selecionadas, transacao READ ONLY comprovada; NAO prova que esta base seja replica recente de producao |
| E4 | Leitura autenticada READONLY no admin de producao, **relatada pelo coordenador Main em 27/10** | 49 ativos, legadas, ranks catalogados, oito slugs ausentes, zero checkout e dois eventos beta; nao foi consulta autenticada deste agente nem dado fornecido pessoalmente pelo usuario |
| E5 | GET anonimo em `https://bonfiretales.com.br`, captura iniciada 2026-10-27T15:59:09.467776+00:00 | Pagina publica, barreiras de login e fingerprints de estaticos; sem cookie/credencial, sem seguir redirecionamentos |
| E6 | Diagnostico da demo antiga informado pelo Main em 27/10; leitura atual do helper ja corrigido, sem executa-lo | Fixture sintetica e causa da discrepancia visual; nao e estado do PG local nem de producao |
| E7 | Fluxo autenticado em producao, **relatado pelo coordenador Main em 27/10, antes do proximo deploy** | GET /perfil/ e POST somente de previa; nao executados pelo coletor deste agente |

E4: caminhos consultados pelo Main:
`/admin/home/tbcosmetico/?all=1`,
`/admin/home/tbcosmetico/?q=lua`,
`/admin/home/cosmeticcheckoutoffer/` e lista admin de `EventCosmeticOffer`.
A busca por lua retornou somente Luar Prateado.
Os detalhes das duas ofertas de evento confirmaram `active=True`, custo zero,
`starts_at=null` e `ends_at=null`.
Nao foi fornecida a listagem nominal completa dos 49 registros; nao se inventou
um diff nominal completo nem um dump de inventario.

## 3. Codigo e refs Git (E1)

| Referencia | SHA observado | Natureza |
| --- | --- | --- |
| HEAD local, branch `jarvis/redesign-6113ea68` | `98d2189d6156f00ce41823106757a828d6f34e02` | Codigo versionado local |
| origin/dev, consulta remota ao vivo | `98d2189d6156f00ce41823106757a828d6f34e02` | Igual ao HEAD no instante consultado |
| origin/main, consulta remota ao vivo | `982715e88265d6120734ab08e0e4ad38bb63afdb` | Outra ref, nao um identificador de deploy |
| SHA implantado em producao | **NAO CONFERIDO** | HTTP de estaticos nao revela SHA de aplicacao |

As refs remotas em cache coincidiam com a consulta ao vivo.
Historico relevante lido: `a810990156aa9c128d5d5ee3ca918ec6082404f4`,
`f70cf26e52ff382edb8ec779e0cdd4eedba1b420` e HEAD acima.
Nao foi feita auditoria/restauracao artistica de P4.

O checkout e compartilhado: durante E1 surgiram mudancas concorrentes em
views, direitos, URLs e templates. Por isso as referencias de codigo abaixo
sao ancoradas explicitamente em **98d2189**, conferidas com `git grep ... 98d2189`,
e nao representam aceite das alteracoes ainda nao commitadas.
A hash de cada estatico foi medida contra os bytes locais no instante de E5.

## 4. Matriz de dados e disponibilidade

| Requisito | Fixture/repositorio | PostgreSQL local E3 | Producao E4 | Estado |
| --- | --- | --- | --- | --- |
| Catalogo efetivo | 24 linhas `home.tbcosmetico` na fixture | 30 linhas, todas ativas | 49 linhas ativas | DIVERGENTE; nao sincronizar por contagem |
| Friso Dourado `moldura-gold-trim` | Fonte seed e fixture; pacote/asset presentes | PK 10, livre, ativo, ambos | PK 10, livre, ativo, ambos | AMBOS; nao recriar/apagar |
| Coroa de Gelo `moldura-frost` | Fonte seed e fixture; pacote/asset presentes | PK 11, livre, ativo, ambos | PK 11, livre, ativo, ambos | AMBOS; nao recriar/apagar |
| Tranca Verdejante `moldura-verdant` | Fonte seed e fixture; pacote/asset presentes | PK 12, livre, ativo, ambos | PK 12, livre, ativo, ambos | AMBOS; nao recriar/apagar |
| 14 molduras + 7 temas de rank (somente dados) | Fontes 0164/0165 presentes; nao estao na fixture de 24 | Ausentes do resultado de catalogo; 0164/0165 nao constam na consulta de migrations | 14 molduras PK 33..46 e 7 temas PK 47..53, ativos | DADOS SOMENTE EM PRODUCAO na comparacao observada; arte nao auditada |
| Ofertas checkout/cash | Codigo/modelo nao equivalem a oferta cadastrada | NAO CONFERIDO | ZERO registros de `CosmeticCheckoutOffer` | Sem oferta monetaria a provar ou ativar |
| Eventos beta | Codigo aceita custo zero e janela nula | Badges beta presentes; ofertas NAO CONSULTADAS | Duas ofertas active=True, `badge-beta-centelha` e `badge-beta-portal`; custo 0; starts/ends null; evento `beta-aberto` | PRODUCAO confirmada via coordenador Main, sem resgate executado |
| Inventario, equipados e direitos por conta | Nao sao comprovados pelo conteudo exportado | NAO CONSULTADO | NAO CONFERIDO por este levantamento nem por E4 | Camada pendente de Main/conta de teste |
| Migrations aplicadas em producao | Arquivos locais existem | Subconjunto consultado abaixo | NAO CONFERIDO | Nao inferir aplicacao porque o catalogo contem ranks |

### 4.1 Oito itens editoriais, separando arte de cadastro

Fonte: `docs/cosmetics/catalog-draft.json:4` e `:7` a `:14`.
`activate_in_production=false`; pendencias: aprovar arte, moeda/preco das luas,
elegibilidade/periodo do Halloween. Esses campos nao sao autorizacao comercial.

| Slug | Repositorio | Catalogo local E3 | Catalogo prod E4 | Manifest publico E5 |
| --- | --- | --- | --- | --- |
| `tema-lua-vermelha` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `tema-lua-negra` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `tema-lua-cristal` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `moldura-lua-vermelha` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `moldura-lua-negra` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `moldura-lua-cristal` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `moldura-vigilia-das-lanternas` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |
| `tema-vigilia-das-lanternas` | Rascunho: ativo=false, staff, ambos | AUSENTE | AUSENTE (E4/Main) | HTTP 200; mesmo conteudo normalizado |

NAO chamar esses registros de "inativos na producao": **nao existem la**,
conforme E4. Tambem nao confundir os oito temas/molduras com os badges de
Halloween que existem no banco local.

### 4.2 Fixture, replica configurada e antecedentes

`home/fixtures/conteudo.json` contem 24 linhas de `home.tbcosmetico`.
A fixture nao e uma consulta viva nem contem inventario de usuario nesta
comparacao. `home/fixtures/conteudo_manifest.json` confirma as mesmas 24
referencias naturais, nao um segundo conjunto de registros.

Slugs das 24 linhas, extraidos por JSON estruturado:

`efeito-aurora`, `efeito-embers`, `efeito-glass`, `efeito-none`, `efeito-soft-glow`, `efeito-starfall`, `moldura-arcane-pulse`, `moldura-ember-ring`, `moldura-frost`, `moldura-gold-trim`, `moldura-none`, `moldura-verdant`, `tema-abissal`, `tema-arcane`, `tema-bonfire`, `tema-bosque-ferico`, `tema-coracao-da-forja`, `tema-custom`, `tema-ember`, `tema-moonlit`, `tema-sangue-e-ouro`, `tema-tempestade-arcana`, `tema-verdant`, `tema-veu-lunar`.

As seis linhas locais adicionais a essa fixture sao: `titulo-mestre-ouro` (PK 29), `moldura-mestre-ouro` (PK 30), `badge-beta-centelha` (PK 40), `badge-beta-portal` (PK 41), `badge-halloween-lanterna` (PK 42), `badge-halloween-lua` (PK 43).
Os oito slugs do draft nao estao na fixture nem nas 30 linhas locais consultadas.
Os dois badges Halloween locais nao foram individualmente reconciliados com
uma listagem nominal completa de producao.

Evidencia das molduras na fixture:
`conteudo.json:52274` (gold-trim), `:52297` (frost), `:52320` (verdant).
Nao existem evidencias de remocao desses tres registros do banco.

Antecedentes de codigo:
- `home/migrations/0048_seed_cosmeticos.py:22`: 18 itens originais; molduras
  gold-trim/frost/verdant na lista. `:53`: seed por slug/get_or_create com
  origem livre, ambos e ativo. Nao executar novamente para "consertar" uma UI.
- `home/migrations/0057_backfill_seed_temas_basais.py:22` e `:46`:
  cinco definicoes legadas e seis temas basais; backfill nao sobrescreve
  definicao manual ja existente. Explica a fixture de 24 sem inferir deploy.
- `home/migrations/0056_wipe_conteudo_demo.py:26`: referencias historicas
  de remocao de titulos/badges demo; uma ocorrencia de slug no historico
  nao prova que ele exista no banco atual.
- `home/migrations/0164_rank_cosmetic_rewards.py:16` e
  `home/migrations/0165_rank_themes.py:17`: fontes de dados/concessao de rank.
  Citadas apenas como dependencias; nenhuma arte/animacao foi examinada ou alterada.
- `home/management/commands/reconcile_redesign_d_pilot.py:18`: tres pilotos
  `tema-forja-de-brasas`, `tema-aurora-glacial`, `tema-circulo-arcano`.
  Sao constantes de um comando protegido, NAO registros locais/produtivos
  comprovados. O comando nao foi executado.

### 4.3 Consulta local protegida

A primeira tentativa de usar python-dotenv falhou por modulo ausente, antes
de conectar. Nao se instalou dependencia. A segunda usou somente o leitor
`_read_env_file` ja existente em `BonfireSite-main/bonfire/settings.py:13`,
extraido por AST, e o driver disponivel no Python de `BonfireSite-main/.venv`.

Somente endpoint loopback foi permitido. Nao se executou `django.setup`,
ORM ou inicializadores de aplicacao. Conexao com
`default_transaction_read_only=on`, `statement_timeout=5000` e
`lock_timeout=2000`; `SHOW transaction_read_only` devolveu `on`.
Consulta limitada a 200 linhas, retornando 30, seguida de ROLLBACK e fechamento.

```sql
BEGIN READ ONLY;
SHOW transaction_read_only;
SELECT "id", "Slug", "Tipo", "Nome", "Origem", "Ativo", "Escopo", "Preco"
FROM "TB_Cosmetico" ORDER BY "id" LIMIT 200;
-- Segunda SELECT: apenas name em django_migrations, app='home',
-- restrita aos oito nomes de migration listados abaixo.
ROLLBACK;
```

Registradas no subconjunto consultado:
0048_seed_cosmeticos, 0057_backfill_seed_temas_basais,
0143_cosmeticcheckoutoffer_cosmeticcheckoutpurchase,
0147_eventcosmeticoffer_eventcosmeticredemption_and_more e
0149_remove_eventcosmeticoffer_event_cosmetic_cost_positive_and_more.

Nao encontradas nesse banco: 0155_redesign_theme_pilot,
0164_rank_cosmetic_rewards, 0165_rank_themes.
Isso descreve a base configurada `postgres`, NAO autoriza migra-la e NAO
estabelece que ela seja o banco DEV dedicado ou uma replica atualizada.
Usar slug como chave natural: os IDs locais 40..43 sao badges, enquanto E4
informa molduras de rank ocupando o intervalo 33..46 em producao.

### 4.4 Demo sintetica antiga: discrepancia de fixture, nao de producao

O Main identificou a fonte em
`[local-path] Bonfas/AmandaBot/scratch/catalog_export_ui_check.py`.
Segundo o relato historico E6, a versao antiga semeava somente dois itens Arcane
e os 21 itens de rank e ainda injetava os oito drafts de luas/Vigilia com
`ativo=True` e `origem=livre`. Ela NAO incluia os seeds basais completos.

Consequencias do dado sintetico antigo:
- Legadas faltando na preview nao significavam registros apagados do banco.
- Luas/Vigilia selecionaveis nessa demo nao significavam acesso concedido,
  cadastro publicado, preco aprovado ou venda autorizada em producao.
- A demo antiga nao serve de baseline de disponibilidade/obtencao, nem de
  evidencia de sincronizacao dos catalogos entre ambientes.
- Direitos reais existentes ou novos direitos efetivamente concedidos nao
  sao invalidados por esse diagnostico. Nao revogar, compensar ou conceder
  inventario com base na fixture.

Na leitura deste agente o Main JA havia atualizado o arquivo: `:21` aponta
para SQLite em diretorio temporario; `:49` prepara essa base de teste;
`:51` a `:59` incluem explicitamente 0048/0057 basais, 0142 Ouro e 0164/0165
de rank. A busca atual nao encontrou injecao de drafts. Essa leitura comprova
o texto atual do helper, NAO reconstrui por linha a versao antiga ja substituida
nem comprova que a nova fixture foi executada. O helper nao foi executado nem
alterado por este agente. A correcao e suas provas pertencem ao Main/Nash.

O Main informou envio ao Nash de A/B frontend controlado e nao bloqueante;
o baseline SQL controlado do Nash e uma evidencia SEPARADA. Esta reconciliacao
nao mediu desempenho SQL, nao reproduziu esses testes e nao lhes atribui
resultados numericos. Nenhum seed lunar/Halloween deve ser aplicado ao PG
ou a producao como parte desta correcao de fixture.

O coordenador Main tambem identificou o servidor de teste antigo em
`localhost:12572` e informou que sera reiniciado com uma fixture de 49 itens
(basais + Ouro + ranks + dois badges beta), sem alterar o DB de producao.
Esse reinicio/novo total NAO foi executado ou verificado por este agente.
Nao confundir essa fixture temporaria pretendida com a fixture JSON de 24,
com o PG configurado de 30, nem com os 49 ativos de producao confirmados em E4.
Igualar contagem a 49 nao substitui reconciliacao nominal por slug e direitos.

## 5. Caminhos de oferta, obtencao e direitos (codigo 98d2189)

| Caminho | Fonte | Contrato observado, sem executa-lo |
| --- | --- | --- |
| Catalogo/escopo | `home/cosmetics.py:95`, `:240`; `home/models.py:2608` | Catalogo filtra ativo; escopo e direitos sao validados no servidor |
| Loja `/cosmeticos/` | `home/urls.py:71`; `home/views.py:3502` | GET autenticado reutiliza a vitrine de checkout, nao lista automaticamente todo o catalogo |
| Compra R$ | `home/views.py:3637`, `:3643`; `home/models.py:2720` | Exige oferta active, nao demonstration, cosmetico ativo e amount>0; POST cria pedido, nao concede por mera previa |
| Concessao paga | `home/cosmetic_entitlements.py:43` | granted_at, inventario e transacao; nao se chamou a operacao |
| Evento/braseiros | `home/views.py:3531`, `:3561`; `home/event_cosmetics.py:32` | Oferta ativa, janela e custo conferidos; request_id/quoted_cost e posse no servidor; personagem pagador quando ha custo, conta beneficiaria |
| Modelo evento | `home/models.py:2775`; migration 0147; `0149...py:40`, `:45` | 0149 permite janelas nulas e gratuidade; nao concluir que beta sem datas e necessariamente invalido |
| Atelie/MM | `home/theme_studio.py:26`; `home/theme_mm.py:13`, `:23`; `home/urls.py:15` | Origem loja_mm, oferta ativa e nao demonstrativa, saldo/flag/requisicao validos; depende de oferta, nao apenas do preco do catalogo |
| Inventario | `home/models.py:2696`; `home/cosmetics.py:157`, `:175` | Inventario, suspensao e origens nao se deduzem de pacote artistico |
| Direitos permanentes | `home/cosmetic_entitlements.py:10`, `:21` | Compras concedidas, resgates de evento e MM nao revertidos sao fontes independentes da suspensao de uma linha de inventario |
| Assets/manifests | `home/cosmetic_packages.py:42`, `:90`, `:99` | Pacote e apresentacao, nao autorizacao; get_package verifica acesso e load_package so carrega midia |

Ponto de reconciliacao para P2: no HEAD, suspender uma linha de inventario NAO
revoga automaticamente um direito permanente de compra/resgate. O plano nao deve
prometer o contrario sem confirmar a regra de revogacao aceita. Nao foi mudada
essa regra nem testada uma conta suspensa nesta etapa.

Zero `CosmeticCheckoutOffer` em E4 tambem nao comprova que existe uma oferta MM
valida no Atelie, pois o caminho MM consulta esse mesmo modelo. Nao criar precos
a partir das constantes do piloto nem ativar demonstracoes para fazer aparecer CTA.

## 6. Cards de personagens nas lojas: requisito recuperado e lacuna

O requisito funcional verificavel nesta etapa vem do plano
`docs/planos/20261026-perfil-cosmeticos-lojas.md:84`: mesmo personagem/contexto
entre selecao, card, saldo e compra; trocar selecao nao pode debitar.
Nao confundir cards de produtos, thumbnails de cosmeticos e cards do comprador.

Busca delimitada: docs/planos, docs/cosmetics, docs/agentes e memoria Jarvis por
"cards lojas"/"cards". Nenhuma dessas consultas recuperou o pedido original
com especificacao visual completa; o registro de memoria encontrado tratava
de compilacao de partials, nao de aprovacao desses cards.
**Pedido visual original NAO RECUPERADO**; nao substitui-lo por uma proposta nova.

| Tela/caminho | Evidencia HEAD | Contexto que um futuro card precisa preservar | Estado de UI produtiva |
| --- | --- | --- | --- |
| Servicos | `home/templates/home/pages/mercado_servicos.html:23`; `home/views.py:17920` | Balcao compartilhado, treinamento/emprestimo vinculados ao personagem ativo | NAO CONFERIDO |
| Oficina | `home/templates/home/pages/oficina_magia.html:28`, `:94`; `home/views.py:18103` | Personagem e carteira do balcao, formularios recebem esse ID | NAO CONFERIDO |
| Mundanos/magicos | `home/views.py:17646`; `home/templates/home/partials/_mercado_balcao.html:23` | Somente personagens do dono; GET/session `mercado_personagem`; trocar contexto nao e comprar | NAO CONFERIDO |
| Comunidade | `home/templates/home/pages/mercado_comunidade.html:21`; `home/views.py:9851` | Seletor comprador por anuncio, carteira debitada e mochila do mesmo personagem | NAO CONFERIDO |
| Mercado do mestre | `home/templates/home/pages/mercado_mestre.html:52`; `home/views.py:15770` | Ha seletor de personagem; nao assumir que MM da conta e carteira da ficha sao o mesmo saldo | NAO CONFERIDO |
| Eventos cosmeticos | `home/templates/home/pages/event_cosmetic_shop.html:21` | Personagem paga braseiros somente quando custo>0; cosmetico vai para a conta; beta gratuito dispensa pagador | Admin de ofertas confirmado E4; fluxo/card autenticado NAO CONFERIDO |
| Checkout R$ | `home/templates/home/pages/cosmetic_checkout.html:26`; `home/views.py:3637` | Beneficiario e a conta; aplicar na ficha e etapa distinta, nao selecionar "comprador personagem" por suposicao | Admin sem ofertas E4; fluxo autenticado NAO CONFERIDO |

O contrato de contexto e os pontos de entrada estao localizados. Implementacao de
cards, interacoes e criterio visual permanecem P6, fora desta entrega.

## 7. Fingerprints publicos HTTP GET (E5)

Host: `https://bonfiretales.com.br`.
Pagina publica de referencia `/perfil/Gaz/`: HTTP 200.
`/perfil/`, `/cosmeticos/` e `/cosmeticos/eventos/`: HTTP 302 para `/login/`,
sem seguir o redirecionamento. Isto comprova barreira anonima, nao erro 404 nem
funcionamento autenticado. Este agente nao mediu SQL, TTFB/LCP controlados ou previa.

### 7.1 Evidencia autenticada adicional do coordenador Main (E7)

- GET de producao `/perfil/` autenticado: HTTP 200, amostra aquecida com TTFB
  aproximado de 378 ms e DOM em 1799 ms, segundo o Main. Nao e baseline
  controlado nem comparacao frio/quente reproduzida por este agente.
- POST de producao **somente** `/perfil/previa/`, reutilizando as selecoes
  atuais da conta QA e CSRF: HTTP 200, 348 ms, 4218 caracteres de HTML,
  `recusados=[]`, segundo o Main. E teste de previa sem persistencia de
  aparencia; nao e POST de salvar perfil, compra ou concessao manual.
- Nao registrar CSRF, cookies, credenciais ou identificadores pessoais da
  conta QA. Este agente nao fez POST; seria incorreto afirmar que o Main
  nao fez nenhum POST, pois E7 inclui expressamente esse POST de previa.
- E7 confirma acesso ao editor e retorno da previa autenticada antes do
  proximo deploy. NAO prova desempenho global, atualizacao de codigo,
  fluxo de compra/resgate, aceite artistico, equipados ou inventario.
  **Inventario nominal de producao NAO LIDO**; reconciliacao por conta fica
  pendente para o Main, com minimizacao de dados pessoais.

Foram usadas URLs/versionadores extraidos da pagina quando presentes:
effects CSS/JS e motifs CSS `?v=2`; presentation/renderer `?v=5`;
catalog CSS/JS `?v=1`. Os manifests e assets nao referenciados diretamente
pela pagina foram consultados em seus caminhos publicos canonicos.
Resposta de CSS/JS: max-age=14400; manifests: max-age=60; datas/ETags no JSON
reproduzivel do coletor. Cache do CDN e versionador NAO sao identificador Git.

SHA-256 bruto dos bytes recebidos e dos bytes locais:

| Caminho sob home/static | HTTP | SHA-256 remoto | SHA-256 local bruto | Comparacao |
| --- | --- | --- | --- | --- |
| `css/components/profile-effects.css` | 200 | `ff7fe1462e0de8606a72091e01e718a9f502e2c3972968e46c589d25b0a2188a` | `adb5b8ab6da1ddda4760d26289b973380be0bdafccf09be755ace069e3bc148e` | LINE_ENDINGS_ONLY |
| `css/components/profile-theme-motifs.css` | 200 | `a9a1be5703b132b53dfb255bc85a22818b9abb153dea19b54a1c0b73863c6aff` | `fce7a17ab0cc1f5761ccf1b4cfeeab900e7be32ec9d33e1d6a275512c7296ccb` | LINE_ENDINGS_ONLY |
| `css/components/cosmetic-presentation.css` | 200 | `4c9be75c5db5dea025c150dfa3a3783dd400df509649b4a298185e24c417b73d` | `5e7d95c576062495d033b99ab52fd4ecb2d777a0759644c068e29d6f17bc869e` | LINE_ENDINGS_ONLY |
| `css/components/cosmetic-catalog.css` | 200 | `1754c3e55d9d417fe6ca973bbcbfa37bdec47a7f2fb4b656e99876034129ab50` | `b692ae11ae95a3b4205a781396eef81edb5ccd345b3da5d9a71b6a24ca680a46` | LINE_ENDINGS_ONLY |
| `css/pages/cosmetic-shop.css` | 200 | `ea160d8ba88d72acfe5ee980bffebc25ab7876dc1034c1b943481e93b36b41c4` | `9c90083098faf67d795b9b90f5e921a11dd0d621aae8b472d0f09ea1f215bd02` | LINE_ENDINGS_ONLY |
| `js/profile-effects.js` | 200 | `245f0c1c80a0cc4c539da101a21d6061283e101fab9d2012659bfa358d83c057` | `e2a42c8386eb82ba5baa42f41e3d8806a0f60b5468b748192c9d0a0db62c7c6c` | LINE_ENDINGS_ONLY |
| `js/tema_swatch.js` | 200 | `9b4af81d08bdfc94d4bda525267de00e48f8de0972d2c5dc4b2bc8176d2e92b8` | `bc052657bf3f2616cf04dbab45e068a8f5f5e91857786ee817446e959c9daf2b` | LINE_ENDINGS_ONLY |
| `js/cosmetic-catalog.js` | 200 | `dfae88dd07bab47a8eaf3d645d52b4c319f9c1d08e6fa9924fb14a213714f0b3` | `1616428bac783e193a8a318f8af054e2d2957e1ba9b71308c7db5ea3a06d43a7` | LINE_ENDINGS_ONLY |
| `cosmetics/renderer.js` | 200 | `263c667dd0fac675e0be9128e7f826481edb66f62932c8a08a8384c3ad0a468a` | `1fef8c67053864245b05e1de0e4f9be6a6a40c693e087318ffb196f01f37914e` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-arcane-pulse.json` | 200 | `e467a954cbacd8c99ec0b7682632f237f66dbd4dfdf29081544207dbd8f0b428` | `e467a954cbacd8c99ec0b7682632f237f66dbd4dfdf29081544207dbd8f0b428` | IDENTICAL_BYTES |
| `cosmetics/moldura-ember-ring.json` | 200 | `746d05c45edb2c2a337d18b2c2768f008d4e7d9404b4368c663443611c77637a` | `746d05c45edb2c2a337d18b2c2768f008d4e7d9404b4368c663443611c77637a` | IDENTICAL_BYTES |
| `cosmetics/moldura-frost.json` | 200 | `415cc279522a40d2718297650060aab54d7ebe7a438d2d42f417f64bac8f4556` | `89b61ed0f7c760ea18c639c816e6bef648bc471d378e9a539ebc2a6fdb68e523` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-gold-trim.json` | 200 | `3680b0839412e26d2774c5962441f5955965a754fa793d96cd697dfb6290fc4c` | `dc7a9f62e247f53b35657bc14ab51e2ab3cea2b1ce4c121968049c291ecec767` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-lua-cristal.json` | 200 | `b91414d53c85ec1e15bc711874fb602952f6d0310fb400da181d95c5663c1577` | `d3773ab6ccb44b20239117f4908649bc6912edf7c88b32335cb1ae41ff1671dc` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-lua-negra.json` | 200 | `1176221936a4c5ea148e7840356f75bde4f5015e0d6c0b82ea317fa251532b5c` | `1cab70ecb55f9ccd0494602f1e492fff9be6a2993827031d3a58997e7b8e13be` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-lua-vermelha.json` | 200 | `c1680045fa55170ca2b7b537c5191a4aea37465f45765e9538713e07cee264a8` | `03639819e5e2d2202e096662e1a43a60983054b0b90096a1379849a8697ac84e` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-verdant.json` | 200 | `4057060ddafd0adba8a7b6d25d566154c1caa48f4becc93e9845c46d926696b4` | `56a12b40587a742ee2b16961be6b7bab8d2c90bf349596ae8536c3fa9f7b325f` | LINE_ENDINGS_ONLY |
| `cosmetics/moldura-vigilia-das-lanternas.json` | 200 | `905f0a2bcafd94db29a1dc6664606c853f6dc97706024f19b4f7798b769dca88` | `8355048cd86c92ce27655900dc817e0ba1c00a73183c4d9638551a66eb0d58e7` | LINE_ENDINGS_ONLY |
| `cosmetics/tema-arcane.json` | 200 | `ac7f752b7627f36e267b4f71522686c57e523ab115e1ddd81aed340926ea5340` | `ac7f752b7627f36e267b4f71522686c57e523ab115e1ddd81aed340926ea5340` | IDENTICAL_BYTES |
| `cosmetics/tema-bonfire.json` | 200 | `3ce9a2b9fcda475fe618efe1f03348f933653296009080f92e2ef79aab91e4b7` | `3ce9a2b9fcda475fe618efe1f03348f933653296009080f92e2ef79aab91e4b7` | IDENTICAL_BYTES |
| `cosmetics/tema-lua-cristal.json` | 200 | `10afcb0adc593196f41bb68296a9ed3fd61fa969b205eb797e43728144bb5c8b` | `de7cf328d724715e7731480246086b05fea12a72c9694dba39a19462cd8b03b4` | LINE_ENDINGS_ONLY |
| `cosmetics/tema-lua-negra.json` | 200 | `e9895eaea52366d47c457e316dac5a2d58f086f240d5397e7cf40569a7b3b75d` | `e811eaf34331aef49c9fec432c42c728381c9d1324d17887a054f57a272bacfc` | LINE_ENDINGS_ONLY |
| `cosmetics/tema-lua-vermelha.json` | 200 | `f999d34318e6b78688ea88faf9a2e917f20093ee01cf037d79e7c229da618554` | `0f519fd4b8835212446fafa19fc2c415f10fee2fcf79682d0333b3e3d30b55bf` | LINE_ENDINGS_ONLY |
| `cosmetics/tema-vigilia-das-lanternas.json` | 200 | `b0fb0ad71fbc01f8152e694766c78af1f5d6058debfaecdf0aa90d851f934422` | `aaad33ea5f346b4c351b96106a11499fc385c576b32fc778e01377837aded347` | LINE_ENDINGS_ONLY |

`LINE_ENDINGS_ONLY` significa que os hashes LF de ambos os lados sao iguais
apos substituir somente CRLF por LF. Nao marcar essas vinte linhas como
"codigo diferente". `IDENTICAL_BYTES` significa igualdade bruta.
Nenhuma dessas relacoes prova SHA implantado, banco, migrations, inventario,
caches de aplicacao, CSS efetivamente vencedor na previa ou aceite artistico.
Em particular, manifest das luas/Vigilia disponivel nao equivale a item publicado.

## 8. Ferramenta e verificacao

`docs/qa/tools/reconcile_readonly.py` usa apenas biblioteca padrao:
AST para constantes de migrations, JSON estruturado para fixtures/draft,
Git de leitura e GET anonimo limitado a 4 MiB, timeout e tres requests paralelos.
Sem escrita de arquivo, .env, Django, DB, cookies ou credenciais. Imprime JSON.
Ignora manifests/midias de rank e JSONs editoriais que nao sao pacotes.
O SQL local E3 foi uma consulta pontual separada, com protecoes documentadas em 4.3.

```powershell
py -B docs/qa/tools/reconcile_readonly.py --offline
py -B docs/qa/tools/reconcile_readonly.py
```

Execucoes offline/online concluidas com JSON valido. Conferidos 15 manifests
nao-rank e existencia de todos os assets referenciados; vinte migrations
relacionadas localizadas, mas somente o subconjunto E3 teve aplicacao consultada.
Nao se executou suite funcional ampla, servidor, navegador ou screenshot.

## 9. Encaminhamento finito ao Main

| Proxima acao | Evidencia que falta | Limite |
| --- | --- | --- |
| Completar mapa nominal prod/local | Export de leitura dos 49 slugs e regras atuais, sem dados pessoais desnecessarios | Nao usar contagem ou PK como plano de sincronizacao |
| Confirmar direitos da conta de teste | Inventario, equipado, suspensao e fatos de compra/resgate | GET/admin/API somente leitura; nao conceder para "testar" |
| Preparar P1 e P2 | Uma abertura e uma troca autenticada; descoberta fora da vitrine de ofertas | Fora de P0; nao afirmar perfil rapido por tamanho de assets |
| Recuperar criterio original de P6 | Relato/aprovacao dos cards de personagem nas lojas | Nao confundir selecao do pagador com card de produto |
| Invalidar baseline de disponibilidade da demo antiga e usar fixture segura | Main/Nash: novo seed basal + Ouro + rank, A/B frontend e baseline SQL separados | Nao injetar drafts no PG nem alterar direitos reais; nao apresentar demo antiga como producao |
| Definir obtencao de luas/Vigilia | Aprovacao editorial, moeda/preco/janela/elegibilidade | Nao cadastrar/ativar/vender nesta etapa |
| P4 e ranks | Permanecem fora do lote atual | Nao restaurar Arcane, substituir arte aprovada ou mexer em animacoes de rank |

Nao foi alterado o plano original nem antecipada implementacao de P1/P2/P4/P5/P6.
