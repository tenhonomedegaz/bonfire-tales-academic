# Lote curto: mercado de mestres e contratos de magias

## Mercado entregue

O resgate permite escolher quantidade (padrao 1, maximo padrao 100). O total e
mostrado antes da confirmacao; o servidor calcula novamente preco e quantidade.
Leilao continua unitario. A compra de slots continua no fluxo proprio.
O historico registra quantidade, preco unitario e total; o efeito da recompensa
continua sendo cumprido pela staff, como antes. Nao foi criada entrega automatica
de produtos que anteriormente dependiam da equipe.

Arquivos:
- `home/master_market.py`: limites, validacao, carteira bloqueada, debito e recibo
  na mesma transacao, token assinado contra reenvio dos novos formularios.
- `home/views.py`: prepara ofertas e delega resgates ao servico.
- `home/templates/home/pages/mercado_mestre.html`: quantidade e totais.
- `home/static/js/master-market.js`: previa e confirmacao; POST sem JS preservado.
- `home/static/css/pages/master-market.css`: apresentacao dos controles.
- `home/test_master_market_quantity.py`: regressao isolada.

## Catalogo: entregue e pendente

Arquivos do leitor:
- `home/versioned_classes.py`: valida contrato generico de concessao por tags.
- `home/class_revision_editor.py`: revisao do contrato pela API comum, sem mudar
  a publicacao nem personagens existentes.
- `home/character_engine.py`: escolha por lista explicita de magias.
- `home/hunter_spells.py` e `home/hunter_traveler.py`: compatibilidade dos pins
  anteriores; concessoes novas passam pelo leitor comum somente sob contrato.
- `home/test_spell_grants_contract.py`: cobertura de listas, niveis e compatibilidade.

Nenhuma regra nova de magia e escolhida pelo nome de um talento ou classe.
O contrato escolhe o leitor; as tags continuam especificando magias e niveis.
Isso ainda nao elimina as outras mecanicas especificas antigas.

## Proxima entrega finita

1. Preparar revisao de dados contra a versao realmente ativa. Reaproveitar o
   Markdown aprovado, excluir apenas do novo snapshot as seis ordens/37 features
   legadas e corrigir progressao de recurso. Nao apagar linhas nem fichas antigas.
2. Adicionar dados das tres concessoes restantes e da escolha de Caminho Final.
   Novas features recebem PK do servidor; nao importar PK de outro banco.
   Antes de ativar o contrato, conferir tambem troca por descanso, custos e usos
   limitados de Caminho Final: conceder magias por tags nao implementa esse estado.
3. Conferir contagem, FK, Markdown e concessoes antes/no nivel de desbloqueio.
   Publicar pelo `class-publication-preview` / `class-publication`, que exigem
   backup verificado no servidor. Nao mudar o env para ativar o novo ponteiro.
4. Com o ponteiro instalado, alterar `home/views.py`,
   `home/templates/home/pages/criacao_ficha.html`, `home/class_catalog_api.py`,
   `home/hunter_views.py`, `home/hunter_publication_diagnostic.py`,
   `home/admin.py` e `bonfire/settings.py`: criador/listagem/publicacao comuns,
   sem exclusao de classe, `?hunter=1` obrigatorio ou fallback operacional por env.
   Os adaptadores de pins antigos continuam separados desta selecao.
5. Apos o deploy desse leitor, ativar `contracts.spell_grants=tags-v1` por revisao
   e publicacao comuns; provar que as concessoes novas nao dependem do fallback.

Nao ativar o contrato antes dos dados nem remover o fallback antes do ponteiro.
Nao reabrir VTT, redesign ou outras mecanicas para concluir este marco.

## Publicacao deste lote

Somente codigo e documentacao. Nenhuma migration nem escrita remota de dados.
O deploy segue o `/site-update` do BonfireBot, executado pelo responsavel.
O mercado fica disponivel apos esse deploy; a unificacao completa do Cacador
continua pendente, e nao deve ser reportada como concluida.
