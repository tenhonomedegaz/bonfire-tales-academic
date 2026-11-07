# Tratamento do QA de conteudo - 02/11/2026

Fonte: `[local-path]`. O arquivo original foi
preservado. As decisoes do Bonfire Nexus descritas nele nao equivalem a uma
aprovacao das regras do site: nao foram usadas para inventar regras faltantes.

## Metodo e integridade

Correcoes feitas em dados de producao, nao por condicionais no motor, migrations
de conteudo ou alteracao de templates especificos por classe/talento.

- Catalogos: API existente, PATCH parcial, If-Match e Idempotency-Key.
- Habilidades de classe: formularios admin existentes, apenas `descricao`.
- Backup dos registros afetados antes de cada escrita; releitura apos gravar.
- PKs, slugs, tags, relacoes, inventarios e personagens preservados.
- Numeros e formulas das nove fichas traduzidas preservados; metadados `_en`
  conservados para consulta da fonte original.
- Nenhum banco local foi restaurado sobre a producao.
- Dados operacionais e backups ficam fora do repositorio do site, em
  `AmandaBot/data/catalog_releases/qa-20261102/`.
- Alteracoes editoriais em revisoes publicadas devem passar pelo contrato de
  revisao/publicacao existente. Nao trocar o ruleset de personagens legados.

## Aplicado e relido

112 registros distintos afetados: 17 magias, 2 talentos, 9 criaturas e 84
habilidades de classe. Algumas habilidades receberam mais de uma correcao.

| Conteudo | Alteracao |
| --- | --- |
| Invocar Celestial e Invocar Fada | Nomes ingleses corrigidos para Summon Celestial / Summon Fey. |
| Conjurar Celestial e Conjurar Fada | Nomes ingleses corrigidos para Conjure Celestial / Conjure Fey. |
| Enraizar | Area escrita como quadrado de 6 m de lado, nao 6 m quadrados. |
| Enraizar, Teia, Agarrao Terrestre, Golpe Enraizador | Terminologia da condicao Restringido/Restringida. |
| Tendoes Umbrais, Telecinese, Rajada e Muralha Prismatica | Restrito/Restrita padronizado para Restringido/Restringida. |
| Canto Funebre | Prostrada substituido por Caida no texto. Tags nao alteradas. |
| Simbolo | Removida a repeticao da medida de 30 pes. |
| Palavra Divina e Banimento | Tipos de criatura: Fada e Corruptor no lugar dos sinonimos inconsistentes. |
| Rajada e Muralha Prismatica | Tabelas reconstruidas em Markdown, 8 e 7 linhas respectivamente, sem mudar efeitos/dados; rotulos de testes padronizados. |
| Enterrado vivo | Margem de sucesso corrigida para 5, nao 1,5 m; terminologia Restringido no texto. |
| Escudeiro do Amanhecer | Pontuacao do subtitulo Golpe Preciso e indentacao da sublista. |
| Marca Anomala Maior | Referencias corrigidas para Fortitude Anomala. |
| Runas Elementais | Concordancia de "as suas manifestacoes". |
| Campeao das Runas | Acentuacao de "criara". |
| Eco Curativo | "metade do dano" e fechamento do parenteses. |
| Espiritos Vingadores | Referencia ao nome singular Escudo dos Antepassados. |
| Santuario do Amanhecer | Parenteses fechado, frases separadas e "esfera de luz". A lista de efeitos ja estava correta na fonte consultada. |
| Golpe de Abertura | Parenteses fechado e regra de erro separada da regra de arredondamento. |
| Espirito de Luta | Removido o "do" excedente de "entra no do estado". |
| 45 habilidades de Guerreiro e 30 de Ladino | Nomes soltos da proxima subclasse retirados do fim das descricoes; nenhuma habilidade/subclasse removida. |
| Ataque Oculto | Acentuacao restaurada, sem reescrever a regra. |
| Sombra do Cacador e Vozes dos Que Partiram | Nomes alinhados a Passos Sem Pegadas / Falar com Mortos e links Markdown para os slugs confirmados por API. |
| Dois cartoes Santuario do Amanhecer | Retirado o rotulo solto Dominio da Morte do fim dos textos. A lista de efeitos ja estava correta na fonte consultada. |
| Invocacoes 922, 926, 927, 928, 929, 930, 931, 933, 934 | Traducao dos trechos residuais de PV/formas/deslocamento e nomes de acoes; nenhum numero novo nem remocao de duplicatas. |

As habilidades de Barbaro/Clerigo tambem foram conferidas nas paginas
publicas, com texto novo presente. Sete ajustes iniciais foram conferidos por
texto integral na pagina, e seis caudas de cartoes (inicio/meio/fim das duas
classes) por amostragem. Os cinco ajustes editoriais finais foram relidos no
admin. Os 28 registros de catalogo foram relidos pela API.
As nove fichas traduzidas ainda nao representam uma revisao integral de todas
as traducoes do bestiario nem resolvem as fichas duplicadas/vazias.

Detalhes exatos e campos antes/depois: `plan.json`, `applied.json`,
`extra-plan.json`, `extra-applied.json`, `class-applied.json` e
`class-public-verified.json`, `navigation-applied.json`,
`navigation-public-verified.json` e `final-applied.json` na pasta acima.

## Correcao ja encontrada na fonte consultada

- Dom do Impeto Telecinetico: espacamento, rotulos Falha/Sucesso e final do
  texto ja estavam corrigidos na producao. Nao foi regravado. A duplicidade
  mecanica com Telecinetico continua sem decisao.
- A busca editorial por Ferrreiro nao encontrou a substituicao exata
  relatada. Nao tratar isso como validacao completa da Armadura Reforjada.
- Redemoinho e a troca da Alianca Selvagem ja constavam como corrigidos no
  relato. As criaturas antigas da Alianca ainda precisam de triagem.

## Proximas correcoes verificaveis

| Frente | Dados / arquivos relevantes | Proxima acao |
| --- | --- | --- |
| Pericia Especializada e ASIs | TbClassehabilidade, TbRecursoclasse, regras de progressao | Conferir os registros reais e as tags antes de criar entradas; nao duplicar concessoes ja calculadas. |
| Aparar / Ripostar | Potencia Psiquica e TbOpcaoJogo | Conferir fonte canonicamente aprovada; a confirmacao de terceiro citada no relato nao basta para trocar mecanica. |
| Graviturgia | Markdown da habilidade; nomes atuais de TbMagia | Mapear as 39 referencias por nome ingles e usar Portugues (English) / link. Nao traduzir por palpite. |
| Mina de Impacto | TbOpcaoJogo.descricao | Padronizar titulo Aprimoramento nos dados. API atual expoe opcao_jogo como somente leitura; usar fluxo administrativo apropriado. |
| Disparo de Banimento | Pagina da classe e TbOpcaoJogo | Comparar textos integrais antes de sincronizar; nao tomar o resumo da API como fonte completa. |
| Fontes Caido/Derrubado | Investida de Aco e Dominio Corporal | Conferir que e realmente a condicao e padronizar apenas o nome. |
| Traducao do bestiario | TbBestiario.statblock_json e descricao_markdown | Revisar os outros IDs do relato; preservar campos ingleses e numeros; evitar traducao global de palavra ambigua. |
| Slug salarin | TbLinhagem.slug e consumidores/exportadores | Auditar referencias antes de mudar chave; preferir compatibilidade de leitura sem romper fichas. |
| Tabelas narrativas | Descricoes de Discordia, Banco de Entropia e Tocado pelo No | Primeiro formatar Markdown sem perder efeitos; dados estruturados depois sob contrato generico. |
| Ausencia de CDs/gatilhos | Tags e descricoes; docs/cds/mapa.md e docs/eventos/mapeamento.md do Nexus | Solicitar os mapas citados, nao fornecidos neste anexo. Nao atribuir 104 CDs por um padrao presumido. |

## Decisoes de regra pendentes

| Ponto | Decisao / fonte necessaria |
| --- | --- |
| Aura do Paladino | Degraus da tabela ou salto unico no 18? |
| Clerigo, espacos de 5o | Confirmar tabela canonica; nao copiar Mago apenas por maioria. |
| Punho do Dragao | Avatar ou Garras/Pilares; niveis 10/11 e tabela de dano. |
| ASIs do Ladino e Guerreiro | Confirmar progressao desejada e conferir concessoes existentes. |
| Furia Devastadora no 17 | Distinguir lembrete de evolucao de nova concessao; nao apagar a linha automaticamente. |
| Feiticaria Inata | Identificar qual caracteristica tem custo divergente. |
| Ferramentas de Trabalho | Identidade dos talentos concedidos; nome/slug atual e efeitos correspondentes. |
| Cavaleiro das Sombras | Limite 3 ou 5 e beneficio de Legiao. |
| Cavaleiro Arcano | Confirmar o quarto truque no 14. |
| Cacador, magias preparadas | Quantidade por nivel ou formula canonica; coluna ausente nao autoriza inventar valores. |
| Reposicionamento Tatico, Vendaval, Pacto Umbral | Confirmar registros legados vs vigentes e remapear referencias antes de desativar duplicatas. |
| Telecinetico vs Dom do Impeto | Confirmar se ambos recebem a mesma represalia. |
| Forca Indomavel | Mesmo nome nao significa mesma habilidade; preservar escopo de classe/subclasse. |
| Tiro Perfurante | Dado de Combate ou Sangue-Frio; confirmar qual versao fica. |
| Protecao / Couraca Primal | Confirmar o nome canonico do aspecto. |
| Baluarte Mortal | Resolver 32/36 m e recuperar a frase truncada original. |
| Ajudante da Natureza e Rastro de Brisa | Resolver divergencia metros/pes; nenhuma distancia foi alterada. |
| Impedido nas magias | Identificar condicao vs simples impedimento de movimento em cada caso. |
| Ruptura da Realidade | Classes com acesso; nao alteradas classes_slugs apenas por conhecimento externo. |
| Armas de Haste | Criar propriedade ou lista explicita; Empunhadura Longa nao foi presumida como equivalente. |
| Segredos do Cacador | Custo base por grau; custo adicional ja citado como corrigido nao resolve o base. |
| Pontos de Conviccao | Fonte do recurso, reserva e recuperacao. |
| Lenda Viva | Ativacao e duracao do estado. |
| Impetos Arcanos | Texto fonte completo para confirmar se esta cortado. |
| Alma Ardente | Alvos hostis/escolhidos e escopo da imunidade de 24h. |
| Efluvio Toxico | Turno do Cacador ou do alvo para a duracao. |
| Forca Runica | Gasta Dado de Combate ou so usa o tamanho do dado? |
| Servo Morto-Vivo | Ataques e melhorias completas nos niveis 9/13/17. |
| Magias de juramento | Listas e niveis por juramento. |
| Estilos de Luta do Cacador | Lista canonica / vinculos de elegibilidade. |
| Possuido | Definicao completa da condicao, nao deduzida de uma frase. |

## Saneamento que exige referencias e preservacao de vinculos

- Itens magicos: identificar os sete pares por PK/slug; definir raridade, slot
  e preco canonicos. Nao excluir ou fundir itens com inventarios vinculados.
- Cristal da Mente: o preco 250 escolhido pelo Nexus nao foi adotado como
  autorizacao para sobrescrever a outra copia.
- Bestiario: as 24 fichas incompletas e Demonio/Demonio Menor precisam de
  fontes completas; o relato nao inclui as imagens do Familiar Primal e do
  Defensor de Aco nem seus blocos completos.
- Pares de invocacoes: resolver referencias de magias/classes/personagens
  antes de remapear ou desativar duplicatas. Nao unir pelo nome apenas.
- Companheiro Draconico sem referencia nao e prova de que pode ser apagado.
  Sacred Statue precisa de traducao confirmada, nao exclusao.
- Criaturas antigas da Alianca Selvagem: distinguir legado de conteudo
  vigente, preservar fichas antigas e impedir novas escolhas quando adequado.

Nao e necessario /site-update para as alteracoes de dados ja aplicadas.
Nao foi criada regra de jogo nova no Python/JavaScript nesta etapa.
