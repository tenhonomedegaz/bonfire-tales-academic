# Plano de execucao: perfil, cosmeticos e lojas

## Estado apos a autorizacao de 27/10

### Continuacao: itens 4 e 5 apresentados ao PO

A numeracao da resposta ao PO nao era a numeracao P0-P7 da tabela abaixo:
4 = recuperar Arcane e submeter composicao estatica antes de replicar;
5 = concluir cards das lojas e publicar pequenos lotes conferidos.
Nao confundir o item 5 com o P5 comercial: precos/eventos continuam sem definicao.

Arcane recuperado e cards implementados localmente. Composicao estatica
aprovada pelo PO, com brisa 2,5D discreta em `../cosmetics/20261027-art-direction.html`; nao equipavel nem
publicada como oferta. Evidencias e arquivos em `../qa/20261027-entrega-4-5.md`.
Direcao visual aprovada expressamente; verificacao apos deploy permanece um
gate explicito, nao concluido por inferencia a partir de commit/push.

Etapas 1, 2 e 3 da ordem apresentada ao PO foram executadas no DEV: conciliacao,
gargalos comprovados de leitura/carregamento e descoberta de nao possuidos.
Evidencias, limites e procedimento de publicacao em
`../qa/20261027-entrega-1-3.md`. Isso nao marca redesenho artistico, obtencao
comercial nova ou cards das lojas como concluidos. Producao depende do deploy.

## Limites desta revisao

Planejamento, nao autorizacao para ativar ofertas, definir precos ou reescrever
artes aprovadas. Nenhuma alteracao funcional nesta etapa. O executor local ficou
sem responder a parte das leituras: nao foi concluida a conciliacao de Git e
bancos. Ausencia de evidencia deve permanecer marcada, nunca virar concluido.

## O que existe e o que nao esta aceito

| Frente | Implementado anteriormente | Falta para considerar entregue |
| --- | --- | --- |
| Perfil | Catalogos visuais, previa e sincronizacao de aparencia | Diagnostico do carregamento inteiro, incluindo GET, previa, SQL, rede e renderizacao |
| Performance | Sete artes de rank em WebP, 91,7% menores | Nao comprova que o perfil inteiro ficou rapido; outras imagens e custo de aplicacao nao foram auditados |
| Ranks | Molduras e temas, concessao permanente retroativa | Animacoes serao alteradas manualmente pelo PO; preservar esse trabalho, fora do proximo lote |
| Tres luas e Vigilia | Artes/manifests e rascunho de oito itens | Publicacao, identidade artistica aprovada e caminho de obtencao real |
| Catalogo/loja | Seletores por tiles e rota /cosmeticos/ | Catalogo de descoberta de itens nao possuidos, com estados e CTA coerentes com ofertas/regras |
| Temas | Paletas, motivos e camadas de efeitos | Recuperar composicao antiga aprovada; substituir padroes desconexos por direcao visual aprovada, admitindo assets estaticos |
| Molduras antigas | Pacotes novos de friso, gelo e folhagem | Conferir registro, estado ativo, inventario, nomes e visibilidade em ambos ambientes; nao recriar ou apagar por suposicao |
| Cards de personagens nas lojas | Implementacao exata ainda nao reconciliada | Recuperar pedido original e mapear cada loja, sem confundir seletor de comprador com cards de itens |

## Evidencias disponiveis

- Commits registrados na entrega anterior: `a810990`, `f70cf26`, `98d2189`.
  Push nao comprova deploy nem sincronizacao do banco.
- Em `docs/cosmetics/catalog-draft.json`, oito itens das luas/Vigilia estao com
  `ativo: false`, `origem: staff` e `activate_in_production: false`. O proprio
  arquivo registra pendencias de arte, moeda/preco e elegibilidade/periodo.
  Isto confirma o rascunho local, nao a situacao viva de cada registro remoto.
- Producao publica consultada em `/perfil/Gaz/`: HTTP 200 e referencias aos
  CSS de efeitos/motivos `v=2` e arte de rank WebP. Esses sinais nao comprovam
  SHA implantado, migrations nem dados iguais aos locais.
- Amostra de navegacao com cache: TTFB 883 ms, primeiro conteudo 3288 ms,
  LCP 3504 ms e load 3828 ms. E uma amostra nao controlada do perfil PUBLICO;
  nao mede o editor privado e nao identifica isoladamente a causa.
- `/perfil/` e `/cosmeticos/` redirecionam visitantes anonimos ao login. Falta
  conferi-los autenticados na producao com a conta de teste existente.
- `home/templates/home/pages/event_cosmetic_shop.html:21` ainda usa select de personagem pagador:
  a ficha paga braseiros e a conta recebe o cosmetico. O checkout em reais
  beneficia a conta; aplicar na ficha e uma etapa diferente. Revalidar esse
  contrato nas outras lojas antes de substituir selects por cards.

## Modelo de disponibilidade

Separar os seguintes conceitos, com regras genericas e dados do catalogo:

1. Rascunho editorial: nao equipavel nem compravel; pode ter vitrine de futura
   colecao se publicada explicitamente, sem expor rascunhos internos por padrao.
2. Publicado e nao possuido: visivel em descoberta, com previa e requisito.
3. Obtenivel agora: CTA aponta para oferta, resgate ou conquista existentes.
4. Indisponivel/exclusivo/periodo encerrado: visivel quando autorizado, explica
   o motivo e nao exibe botao de compra/resgate sem operacao valida.
5. Possuido: pode equipar nos escopos permitidos; suspensao/revogacao permanece
   respeitada, mesmo com previa artistica publica.

Nao derivar preco de nome/raridade; nao transformar staff em gratuito. Separar
pre-visualizar arte de conceder inventario. Reutilizar os fluxos transacionais
de compra/resgate ja existentes, com idempotencia e validacao no servidor.
Se `ativo` estiver acumulando visibilidade, publicacao e elegibilidade, primeiro
propor um contrato separado e verificar se exige mudanca estrutural. Nao ativar
um rascunho para simplesmente conseguir mostrar sua previa ao publico.

## Decisoes a recuperar, nao repetir

Consultar decisoes anteriores antes de perguntar novamente sobre moeda/preco,
periodo do evento ou elegibilidade. So levar ao PO o que estiver realmente sem
definicao. A aprovacao artistica de uma referencia nao equivale a aprovar venda.
Para o padrao Arcane, recuperar o arquivo/commit aprovado; se houver mais de uma
versao candidata, apresentar comparacao visual para identificar a correta.
Nos cards das lojas, recuperar o requisito e seus relatos antes de propor um
novo design. Nao exigir que o PO reescreva tudo que ja foi registrado.

## Sequencia e criterios de aceite

| Etapa | Trabalho delimitado | Dependencia | Aceite |
| --- | --- | --- | --- |
| P0 - Conciliar | Manifesto por requisito com SHA local/remoto, assets, registros por slug, inventario e ofertas; localizar relatos dos cards | Executor local acessivel | Cada item marcado dev/producao/ambos/ausente/nao conferido; nenhuma linha encerrada so por screenshot local |
| P1 - Medir perfil | Uma abertura e uma mudanca de previa, frias/aquecidas, privado/publico; duracao SQL, repeticoes, rede, JS e imagens | P0 parcial | Baseline reproduzivel e gargalos comprovados, sem diagnostico baseado so no tamanho das artes |
| P2 - Descoberta | Catalogo completo de itens publicados; filtros tipo/colecao/disponibilidade e busca; recuperar molduras antigas | P0 | Nao possuido ve previa/requisito; suspenso nao equipa; itens antigos preservam slug/PK/inventario |
| P3 - Corrigir desempenho | Corrigir maiores custos medidos: consultas repetidas/N+1, montagem da previa, recursos bloqueantes ou midias, conforme evidencia | P1 | Comparacao antes/depois equivalente; meta numerica fixada apos baseline; sem vazamento de direitos entre contas |
| P4 - Aprovar arte | Recuperar padrao Arcane aprovado; uma composicao estatica com animacao complementar; uma proposta lunar com identidade clara | P0 | PO aprova uma referencia em perfil privado/publico, ficha e miniatura antes de replicar colecoes |
| P5 - Obtencao | Definir moeda/preco das luas e regra/periodo da Vigilia; ligar CTA a compra/resgate/conquista real | P2 e decisao editorial | Resgate/compra concede uma vez e equipa; repeticao segura; periodo e inelegibilidade explicados |
| P6 - Cards nas lojas | Aplicar componente e comportamento confirmados a cada loja afetada | P0 e recuperacao do pedido original | Mesmo personagem/contexto entre selecao, card, saldo e compra; nenhum gasto por trocar a selecao |
| P7 - Publicar lote | Previa de dados, backup, commit/push, /site update e verificacao remota curta | Etapas aceitas do lote | Codigo e dados conferidos no destino; pequena matriz remota comprova o que foi publicado |

P1, P2 e levantamento de P6 podem ocorrer em paralelo, com arquivos e donos
separados. P3 depende da medicao; P5 depende de regras aprovadas. P4 pode ser
adiantado como proposta visual, mas nao substituir a arte antiga antes do aceite.
Publicar marcos utilizaveis: nao esperar toda a arte para corrigir performance,
nem chamar a colecao de pronta enquanto nao houver obtencao.

## Arquivos e pontos de inspecao

- Perfil: `home/views.py` (`profile_view`, `perfil_preview_view`,
  `_appearance_context`), `home/templates/home/pages/perfil.html`,
  `home/templates/home/partials/_perfil_publico_hero.html` e scripts da previa.
- Direitos/catalogo: `home/cosmetics.py`, `home/cosmetic_entitlements.py`,
  `home/rank_cosmetic_rewards.py`, `home/event_cosmetics.py`, modelos de
  cosmeticos/inventario/ofertas e migrations 0048, 0143, 0147, 0164 e 0165.
- Vitrine: `home/templates/home/includes/cosmetic_catalog.html`,
  `home/templates/home/pages/cosmetic_checkout.html`,
  `home/templates/home/pages/event_cosmetic_shop.html`, `home/urls.py`.
- Arte/tema: `home/static/cosmetics`, `home/static/js/profile-effects.js`,
  `home/static/css/components/profile-theme-motifs.css`, `profile-effects.css`,
  `theme-compositions.css`, `home/cosmetic_packages.py` e renderer compartilhado.
- Cards: `home/templates/home/pages/event_cosmetic_shop.html` tem o seletor;
  `mercado_servicos.html` usa `mercado_ativo` e formularios com contexto do
  personagem. Conferir tambem `oficina_magia.html`, `mercado_mestre.html`,
  `mercado_comunidade.html` e componentes compartilhados do mercado. A lista
  exata de mudancas depende de recuperar o requisito original, nao apenas
  desses nomes de arquivos.

## Regras de execucao

- Um requisito tem evidencia de codigo, dados, interface e destino. E preciso
  distinguir implementado, testado localmente, publicado e aceito pelo PO.
- Testes pontuais por mudanca; smoke integrado por marco. Nao repetir suites
  amplas ou rodadas de cosmetica sem criterio de aceite novo.
- Nao criar condicionais Python por nome de cosmetico, loja ou criatura para
  esconder dados inconsistentes. Conteudo no banco; arte em assets/manifests;
  renderizacao e acesso em contratos genericos.
- Preservar o padrao Arcane aprovado e os PNGs/artes anteriores ate aprovar a
  substituicao. Evitar CSS acumulado que sobrescreve silenciosamente o anterior.
- Nao retomar Jarvis/metas, ativar cobranças ou alterar ranks nesta revisao.
