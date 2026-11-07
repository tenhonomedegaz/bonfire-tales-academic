# Lote de manutencao - 26/10/2026

## Entregas

### Relatos de Schmidt

- Busca de missoes: o estilo geral de inputs da area de mestres sobrescrevia
  o padding da lupa. Wrapper e regra especifica reservam 42px para a busca.
  No celular, o flex-basis e automatico para nao esticar o campo verticalmente.
  A versao do CSS foi atualizada nas quatro telas que o carregam.
- Menu Mundo: removido o grupo Lore que repetia Organizacoes e Cronicas.
  Os destinos de navegacao ficam uma vez, em Atlas ou Publicacoes.
- Pedido de mestre: continua sendo registrado em TbPerfilMestre, com avaliacao
  manual da administracao em `/mestre/central/#permissoes`. Nao e enviado ao
  Discord nem concede acesso automaticamente. A aba Mestre agora informa esse
  destino e a data de envio; administradores recebem um atalho para a fila.
- Central: pendentes por padrao, mais antigos primeiro, filtro por estado e
  solicitante e paginacao de 25 registros. Pedidos nao ficam mais escondidos
  atras de um corte de 100 perfis aprovados. Confirmacao, controle de versao,
  autorizacao e CSRF permanecem exigidos para qualquer decisao.
- Admin: atalhos para solicitacoes de mestre e exportacao. A busca numerica e
  textual de itens mundanos foi conferida em banco de teste, sem novo remendo.

### Exportador

Incluido o exportador local ja desenvolvido: `/admin/catalog-export/`, somente
superuser. Selecao de tabelas, campos, filtros, periodo quando ha campo de data,
previa assinada e XLSX. Sem alteracao de catalogo, sem senhas, autenticacao ou
dados de jogadores no escopo automatico. Detalhes em `docs/catalog_export.md`.

### Correcao de dado editorial

A duplicidade de Joalheria tinha uma causa no banco, nao no motor de filtros:
o Anel do Comando Elemental (slug `anel-do-comando-elemental`, PK 101) possuia
`loja = Joalheiria`. Corrigido somente esse campo para `Joalheria` pela API.

- Previa: uma atualizacao, nenhuma criacao; copia anterior do registro.
- Aplicacao: If-Match e chave idempotente, sem substituir PKs.
- Releitura: 946 identidades anteriores preservadas, 946 registros depois.
- Pagina publica: um unico grupo Joalheria, sem o rotulo com erro de digitacao.
- O mesmo campo do fixture foi corrigido para o sync de conteudo nao restaurar
  a grafia antiga. Nao foi criado alias de loja ou caso por item no Python.
- Recibos locais: `AmandaBot/data/catalog_releases/2026-10-26T05-17-39-947Z-29560865/`.

### Fontes

Repostos `OFL-FrankRuhlLibre.txt` e `OFL-OpenSans.txt` a partir do commit
`7289711136e340afe5a13ba397ecce978071896d` do frontend. Os dois arquivos de fonte
atuais foram comparados com a referencia e sao identicos; nao houve troca de fonte.

## Verificacao

- 19 testes focados: exportador, navegacao, pedido/fila, filtros/paginacao,
  permissoes, confirmacao/versao, CSRF, busca admin e regressao do fixture.
- Interface local com SQLite descartavel: desktop e mobile, lupa com 13px de
  folga horizontal e alinhamento vertical central; menu Mundo sem links de lista
  duplicados; fila com 27 pedidos em paginas de 25 e 2; aba Mestre informa destino.
- Exportador: download local e conteudo XLSX conferidos no lote anterior,
  testes repetidos nesta integracao. Nao foram inseridos dados ficticios em producao.
- A pagina local de missoes usa ambiente isolado sem banco do bot: a conferencia
  prova o layout da busca, nao uma nova validacao da integracao de missoes.

Nao ha migration ou dependencia nova neste lote. Deploy pelo `/site update`
habitual, incluindo estaticos. A unica escrita de producao deste trabalho foi a
correcao editorial de loja descrita acima. Nenhuma solicitacao real foi aprovada.

## Acesso e aviso da fila de mestres

O contexto compartilhado `home.context_processors.master_review` fornece o
acesso e a contagem de pedidos pendentes, sem depender de cada view preencher
`can_authorize`. A vitrine antes nao recebia essa variavel e escondia o atalho.

- Menu Mestre (Gestao), menu mobile e navegacao de mestragem apontam para a
  fila filtrada em pendentes; o link permanece disponivel quando a fila zera.
- Com pedidos pendentes, um aviso abaixo do cabecalho aparece em todas as
  paginas que usam a base do site. O painel inicial do admin mostra a contagem.
- Restrito a superusers ativos ou staff ativo com `home.autorizar_mestres`,
  exatamente a permissao ja exigida no endpoint de avaliacao.
- A contagem e lida do banco ao renderizar a pagina, sem polling nem disparos
  Discord. Recarregar reflete novos pedidos ou decisoes. Usuarios comuns e
  anonimos nao consultam a fila nem recebem contagens.
- 12 testes focados passaram, incluindo contexto por permissao, navegacao na
  vitrine e retirada do aviso apos avaliar um pedido sintetico. Layout conferido
  em 1440 e 390 pixels, sem overflow horizontal. Nenhum pedido real alterado.
- Sem migration. Ativar com `/site update`, incluindo coleta dos estaticos.

## Pendencias fora do lote

Permanecem as quatro mecanicas epicas adicionais declarativas, a matriz ampla de
classes/subclasses, mudancas de politica/economia e o formato especifico Foundry.
Nao foram inventadas novas regras de jogo, aprovados pedidos, alterados saldos,
recriados personagens nem restaurado um banco completo para fechar este lote.
