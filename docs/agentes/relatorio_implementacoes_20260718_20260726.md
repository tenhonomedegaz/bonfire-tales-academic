# Relatorio de implementacoes recentes

Periodo coberto: 18 a 26 de julho de 2026.

Este documento consolida o historico do Git, os relatorios de agentes e o
estado local ainda nao commitado. Ele separa o que ja foi entregue no branch
`dev` do que foi implementado na rodada atual.

## Resumo executivo

As implementacoes recentes tiveram quatro objetivos:

1. fazer criacao e progressao de personagem consumirem as tags como linguagem;
2. corrigir os fluxos encontrados pelos playtests;
3. sanear o vocabulario mecanico e remover semanticas especificas ou ambiguas;
4. criar um laboratorio de builds sem persistir personagens.

O criador, o level-up, a ficha e o Pathbuilder compartilham o mesmo
`character_engine`, o mesmo resolvedor de `pick:*` e os mesmos catalogos. O
Pathbuilder materializa uma ficha real dentro de uma transacao marcada para
rollback, executa `derive()` e devolve apenas o estado serializado.

## Linha do tempo

### 18 de julho

- Temas de ficha passaram a ser aplicados como dados, com previa ao vivo.
- Itens equipados passaram a alimentar o `derive()` de verdade.
- O registry de escolhas ganhou `pick:pericia`.
- O level-up em lote passou a funcionar sem recarregar a pagina.
- O mercado foi reorganizado como catalogo.
- Tags residuais, skills e duplicidades de conteudo foram saneadas.

Commits principais: `11a9a59`, `938eaa5`, `a3d535a`, `b78e173`,
`22c320b`.

### 19 de julho

- Deduplicacao de progresso de Metamagia.
- Picks declarados em talentos passaram a ser descobertos.
- Remodelagem do motor de tags em duas rodadas.
- Perfil de ataque, expertise, grants fixos e `modify` foram ampliados.
- Centenas de tags foram saneadas e o restore consolidado foi atualizado.

Commits principais: `e2a4143`, `eb4b3e3`, `be9865a`, `e20535d`.

### 20 de julho

- Linhagem e Essencia passaram a ser mutuamente exclusivas.
- Expressoes condicionais deixaram de vazar para valores estaticos de dano.
- O validador passou a rejeitar `if()` em contexto estatico.
- Bugs da primeira onda de beta do criador foram reproduzidos e corrigidos.
- Registro de aventuras ganhou historico, rollback e protecao contra duplo
  clique concorrente.
- O campo legado de subclasses foi removido de `TbMagia`.
- Correcoes de CA de escudos e do admin foram entregues.

Commits principais: `e59ed9b`, `0e91c96`, `4f61fbe`, `d708d4a`,
`f13c6e3`, `a312e0c`, `4f28b76`.

### 21 e 22 de julho

- Foi criada a pagina dedicada de subir nivel.
- Pre-requisitos de conjuracao passaram a usar um detector unificado.
- O teto de magia passou a vir da tabela real de slots da classe.
- Troca de magia ficou limitada a uma por nivel.
- Paladino preparado, marcas de lista e terceira leva da staff foram
  corrigidos.
- Maestria de Arma passou a ter duas etapas: arma e maestria daquela arma.
- Itens de missao ganharam fluxo proprio.

Commits principais: `63ea5f6`, `153b12f`, `bc976f8`, `6a763f1`,
`76f1ec2`, `71ae89e`, `46bdf28`.

### 23 e 24 de julho

- Picks de uso, internos a `trigger`, `instant` ou `while_active`, deixaram de
  virar pendencias permanentes do wizard.
- Edicao de ficha e level-up passaram a usar `fetch`, mantendo fallback PRG.
- Multiclasse ganhou contexto explicito de classe para subclasse, opcoes e
  magias.
- Cotas de magia passaram a ser contabilizadas por classe.
- O parser de `::toggle` deixou de renderizar HTML como codigo.
- Equipabilidade de itens ganhou auditoria e protecao no motor.
- O exportador de restore consolidado se tornou reproduzivel.
- Talento humano geral foi desambiguado do talento de origem pelo universo da
  tag.
- A quarta leva recebeu regressao automatizada.
- O Bardo foi substituido integralmente pela versao reworkada: habilidades,
  subclasses, recursos, Acordes e Bailados antigos foram removidos antes da
  importacao canonica.
- O backup `20260724_232711` foi comparado ao PostgreSQL local. O conteudo
  mecanico era identico; wiki, mapa, organizacoes e dados vivos estavam mais
  novos no backup.

Commits principais: `ecef27b`, `a77ecf9`, `2395d26`, `78f3488`,
`d574be0`, `04d6402`.

## Motor de tags no estado local

O trabalho posterior aos commits acima ainda esta no worktree e inclui:

- lexer, parser, AST e evaluator dedicados no pacote `home/tag_engine`;
- exigencia de verbos em `snake_case`, reservando `-` para subtracao;
- semantica de escopo para operacoes externas e internas a blocos;
- separacao entre `restriction`, `prereq` e efeitos que restringem o alvo;
- generalizacao de condicoes, negacoes, dados definidos por habilidade e
  sentidos;
- separacao entre darkvision e devilsight;
- remocao ou reescrita de tags narrativas, legadas e especificas;
- migracoes `0066` a `0084` para aplicar o saneamento ao conteudo;
- inventario completo das tags em
  `docs/agentes/listagem_tags_cadastradas_20260726.md` e `.csv`.

## Pathbuilder

### Base entregue

- usa o criador real para montar o nivel 1;
- compara Build A e Build B;
- aceita niveis de classe, multiclasse e subclasses;
- aceita bonus de atributo, talentos, itens e magias;
- respeita equipamento e sintonizacao no estado derivado;
- nao cria personagem nem relacionamentos persistentes;
- guarda o rascunho da aba em `sessionStorage`.

### Ampliacoes desta rodada

1. **Escolhas genericas**
   - O laboratorio lista qualquer `pick:*` resolvivel pelo registry.
   - Universo, validacao, persistencia temporaria e readback usam
     `home.picks`.
   - Menus dependentes podem abrir novas escolhas em passagens sucessivas.
   - Maestria de Arma usa o valor composto arma + maestria.
   - Um tipo sintetico criado apenas em teste foi resolvido sem codigo novo no
     Pathbuilder.

2. **Modo Livre e Validar regras**
   - Livre mantem o laboratorio permissivo.
   - Validar regras aponta subclasses, picks, ASIs, sintonizacao, armaduras e
     escudos incoerentes.
   - O limite de sintonizacao vem do estado derivado, inclusive progressao de
     Artifice.

3. **Comparacao mecanica**
   - Diferencas de PV, CA, iniciativa, deslocamento e proficiencia.
   - Habilidades ganhas e perdidas entre A e B.
   - Atributos e vitais divergentes ficam destacados.

4. **Progressao**
   - Habilidades sao agrupadas pelo nivel de aquisicao.
   - A progressao reflete as features efetivamente ativas na build.

5. **Conjuracao**
   - Exibe atributo de conjuracao, CD, ataque magico e slots por nivel.
   - Continua distinguindo conjuradores da multiclasse.
   - Lista magias, preparacao e origem.
   - Estruturas de pacto/misticismo continuam vindo do painel de magia real.

6. **Combate**
   - Exibe melhor bonus de ataque, maior dano medio parseavel, quantidade de
     perfis e iniciativa.
   - Mantem a tabela completa de ataques e recursos.

7. **Versoes e portabilidade**
   - Salva ate 30 versoes nomeadas no `localStorage`.
   - Carrega e exclui versoes sem tocar no banco.
   - Exporta e importa um JSON versionado contendo base e Builds A/B.

## Validacao

- `python -m py_compile home/pathbuilder.py`: aprovado.
- `node --check home/static/js/pathbuilder.js`: aprovado.
- `manage.py check`: aprovado.
- `home.test_pathbuilder`: 6 testes aprovados.
- Os testes verificam rollback de personagem, classe, atributos, talentos,
  itens, magias e escolhas.

## Limites conhecidos

- A progressao mostra o nivel de aquisicao dentro da classe. A ordem exata de
  uma sequencia intercalada de multiclasse ainda nao e autoria da build.
- O modo de regras diagnostica os principais limites, mas nao substitui o
  wizard de level-up para cada decisao historica de ASI e troca de magia.
- Compartilhamento atual usa arquivo JSON; nao ha link publico no servidor.
- Importar uma ficha existente e converter uma build valida em personagem
  continuam reservados para uma etapa posterior, pois exigem regras explicitas
  de permissao e persistencia.

## Estado de versionamento

O Pathbuilder ampliado, o motor de tags local, as migracoes `0066` a `0084` e
os relatorios associados ainda devem ser revisados como um conjunto antes de
commit e deploy. O worktree tambem contem mudancas anteriores; nenhuma delas
foi revertida por esta rodada.
