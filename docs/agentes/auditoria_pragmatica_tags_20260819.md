# Auditoria pragmatica das tags - 2026-08-19

## Escopo

Varredura do DSL em classes, habilidades de classe/subclasse, opcoes, antecedentes,
essencias, tracos raciais, talentos, itens mundanos, itens magicos, magias e bestiario.
O criterio foi separar:

1. tag semanticamente e pragmaticamente correta;
2. tag correta, preservada como AST, mas ainda dependente do executor de combate/VTT;
3. tag valida no lint, mas incapaz de produzir a mecanica descrita no consumidor atual;
4. cobertura ausente ou dado ambiguo que exige afericao de conteudo.

## Resultado estrutural

- 3.518 registros auditados;
- 2.624 registros com tags;
- 8.793 linhas de tag;
- `ERROR=0`, `WARN=0`;
- nenhuma referencia quebrada, delimitador desbalanceado ou verbo desconhecido.

## Correcoes aplicadas

Foram alterados 212 registros de conteudo, alem do motor e da biblioteca.

- Recursos agora avaliam formulas com qualquer variavel numerica do contexto, como
  `cha_mod`, `wis_mod` e `spell_mod`, alem de `lvl`, `classlvl` e `pb`.
- `attr_max:<recurso>=<formula>` passou a ampliar genericamente o teto de qualquer
  recurso. Isso cobre Moedas do Contrato sem condicional por classe no motor.
- `ca:+N` deixou de classificar automaticamente um item como escudo. Armadura e escudo
  sao identificados pelo catalogo/slot; aneis, mantos, cajados e acessorios aplicam o
  bonus geral sem virar um escudo invisivel.
- Municao passou a ser consumivel de catalogo. Em item magico, `consumable` voltou a
  ser a autoridade mecanica, com slot/tipo apenas como compatibilidade.
- 143 itens permanentes com cargas perderam `consumable`: gasta-se a carga, nao uma
  unidade inteira do item.
- Truques concedidos por marcas, Portador da Luz, Runas Elementais, Velar o Corpo,
  Magia das Sombras e Mascara da Comunidade agora usam `at_will` e
  `always_prepared` quando devem ser aprendidos.
- Segredos Misticos de conjuracao livre agora declaram `at_will`.
- Consultar os Espiritos passou a declarar pool compartilhado e custo alternativo de
  Furias, em vez de dois casts ilimitados.
- Efeitos permanentes equivalentes a magias deixaram de ser modelados como uma acao
  `cast`: Vinculo Natural, Sangue Elemental, Andarilho das Profundezas e Liberdade
  Absoluta usam `effect{spell:... duration:permanent}`.
- Evolucao Tenebrus passou a ter uso independente por magia.
- Ritualista ganhou um pick real fora de `define{}`; Adepto Marcial nao deixa mais um
  `swap:long_rest` irmao vazar para todas as escolhas.
- Sentidos foram normalizados com `range:` e unidades em pes nos casos confirmados,
  incluindo mantos, mascaras de dragao, Viseira de Danoth, Adaga da Visao Cega,
  Visao no Escuro e Visao Verdadeira.
- Mascaras de Dragao agora aplicam `ca:+cha_mod` apenas sem armadura e nao concedem
  Visao Cega permanentemente; ela e uma ativacao de 5 minutos, 1/descanso longo.
- Defensor nao concede mais CA fixa. A transferencia de ate 3 pontos do bonus da arma
  foi declarada como operacao da primeira jogada do turno.
- Vara de Alerta nao concede mais CA fixa fora da luz: o bonus esta dentro da aura.
- Corrente Efreeti e Corrente Elfica foram classificadas no slot de armadura.
- Dois statblocks corrigidos: Undead Artillery `hp:=52` e Undead Soldier `hp:=51`,
  inclusive no JSON interno do statblock.
- Tags puramente narrativas de forrageio e marcha forcada foram removidas dos
  antecedentes e da biblioteca. Elas nao sao mecanicas executaveis do site.
- Foi criado o primitivo generico `ends_on`, usado no ciclo de vida das asas
  angelicais, Alma Astral e clones de sombra. `overflow:replace_oldest` descreve
  colecoes limitadas sem um verbo exclusivo da Duplicata das Sombras.

## Cobertura atual

| Modelo | Total | Com tags | Sem tags |
|---|---:|---:|---:|
| Classe | 13 | 13 | 0 |
| Habilidade de classe/subclasse | 889 | 816 | 73 |
| Opcao de jogo | 289 | 209 | 80 |
| Antecedente | 30 | 30 | 0 |
| Essencia | 4 | 1 | 3 |
| Traco racial | 352 | 351 | 1 |
| Talento | 139 | 139 | 0 |
| Item mundano | 302 | 109 | 193 |
| Item magico | 946 | 670 | 276 |
| Magia | 580 | 450 | 130 |
| Bestiario | 920 | 506 | 414 |

Esses numeros sao fila de cobertura, nao 964 erros automaticos. Linhas table-only,
entradas narrativas e registros incompletos precisam ser classificados antes de ganhar
tags. Nao se deve preencher o vazio com uma tag sem operacao apenas para elevar a taxa.

## Lacunas confirmadas

### Executor de combate/VTT

O avaliador ja preserva operacoes de ataque, dano, salvaguarda, area, condicao,
conjuracao, invocacao, gatilho e duracao. A ficha atual materializa somente o subconjunto
estatico: CA, PV, iniciativa, proficiencias, resistencias, imunidades, sentidos,
deslocamento, pericias, quantidade de ataques e bonus/CD de magia. Portanto, milhares de
operacoes corretas de magias e criaturas ainda sao declarativas. Retaggear essas linhas
nao resolveria: falta o consumidor de runtime do VTT.

### Cargas de itens

Ha 144 itens com `charges`. O dado agora distingue corretamente carga de quantidade do
item, mas ainda falta um ledger persistente de cargas por `TbPersonagemItem`, com reset,
consumo e destruicao quando a descricao mandar.

### Consumiveis ambiguos

Restaram 113 itens com `consumable` fora dos slots/tipos obvios de pocao, pergaminho ou
municao. O conjunto mistura consumiveis reais (fichas de pena, gemas elementais, pos,
manuais) e residuos claros (amuletos, armas e armaduras permanentes). Nao foi feita uma
remocao cega porque frases como "o item e destruido" tambem aparecem em propriedades
secundarias de itens permanentes.

IDs para afericao de conteudo:

`1, 4, 16, 28, 106, 109, 111, 150, 169, 175, 176, 181, 215, 232, 235, 247, 250,
257, 260, 285, 298, 326, 334, 400, 401, 410, 411, 412, 413, 414, 422, 433, 437,
439, 444, 446, 447, 448, 449, 450, 451, 509, 522, 523, 530, 556, 561, 572, 573,
574, 575, 576, 577, 578, 580, 584, 638, 641, 642, 643, 662, 666, 668, 671, 687,
689, 690, 691, 699, 757, 763, 769, 779, 792, 793, 794, 795, 796, 797, 798, 799,
800, 801, 802, 803, 804, 806, 808, 809, 810, 811, 812, 813, 818, 819, 820, 821,
835, 857, 858, 859, 860, 862, 893, 894, 895, 896, 905, 906, 907, 934, 944, 948`.

### Magias sem lista

Quinze magias nao possuem lista de classe: Codificar Pensamentos, Ferroada Exaurente,
Ampliar Gravidade, Bolso de Pulso, Favor da Fortuna, Objeto Imovel, Onda Pulsante,
Sumidouro Gravitacional, Derivacao Temporal, Fissura Gravitacional, Atar Essencia,
Estrela Negra, Ruptura da Realidade, Devastacao Temporal e Vazio Voraz. Varias sao de
cenarios/fontes especiais; devem ser aferidas contra a fonte, nao atribuidas a Mago por
suposicao.

### Custos e ciclos ainda sem estado canonico

- Despertar da Alma Astral custa 5/4/3 Ki conforme duas outras habilidades ativas. A
  duracao e os eventos de termino foram corrigidos, mas falta um operador generico para
  contar referencias ativas antes de substituir o custo fixo.
- O Terceiro Olho e opcoes semelhantes dependem de um estado escolhido em descanso. As
  tags estao declaradas, mas o executor de estados temporarios ainda e futuro.
- Bestiario possui 414 entradas sem cobertura mecanica completa; as 506 taggeadas ainda
  dependem do executor de combate para acoes, ataques, conjuracao e reacoes.

## Verificacao

- `manage.py validate_tags --max 100 --no-color`: `ERROR=0`, `WARN=0`.
- `manage.py check --no-color`: sem problemas.
- `py_compile` nos modulos alterados: sem erros.
- Contratos pontuais no PostgreSQL, em transacao revertida: formulas por atributo,
  `attr_max` generico, CA de anel sem virar escudo, municao consumivel e item com cargas
  nao consumivel.
- A suite Django direcionada foi interrompida porque a criacao do banco de testes ficou
  acima de 2 minutos sem produzir resultado; nao foi repetida para evitar custo inutil.

## Implementacao fora de combate - 2026-08-20

As lacunas de runtime que pertencem ao site foram implementadas sem adicionar casos por
classe, habilidade, magia ou item:

- `TbPersonagemRecurso` agora possui chave canonica, origem, politica de reset,
  recuperacao parcial e vinculo opcional com a instancia de item;
- cargas de itens sao persistidas separadamente de `qtd`, aceitam reset por amanhecer,
  descanso ou formula em dados e preservam o item enquanto restarem cargas;
- itens empilhados agregam o total de cargas sem converter cargas em quantidade;
- o estado das cargas acompanha o item quando ele e anunciado, comprado ou devolvido no
  mercado da comunidade;
- recursos de classe e pools criados por `define{}` chegam a ficha como contratos
  estruturados, sem reconstruir mecanica a partir do texto exibido;
- slots, usos inatos, pontos de conjuracao e recursos de classe usam o mesmo servico
  transacional de gasto e recuperacao;
- descanso curto, descanso longo e amanhecer disparam eventos genericos de reset;
- `TbPersonagemEstado` registra efeitos persistentes fora de combate e seus eventos de
  termino; a Oficina de Magia mostra e permite encerrar esses efeitos;
- O Terceiro Olho declara uma escolha `swap:short_or_long` e ramifica os quatro
  beneficios com operacoes genericas (`detect`, `sense` e `read`).

Migration obrigatoria: `0101_tbpersonagemestado_tbanuncioitemmagico_estado_json_and_more`.

Testes pontuais executados: cinco contratos novos de recurso/estado, consumo de item,
descanso, compatibilidade AJAX por slug e conjuracao persistente na Oficina. Todos
passaram. O lint global permaneceu em `ERROR=0`, `WARN=0`.

## Fronteira com o VTT

Ataques, dano/cura em cena, salvaguardas, testes, alvos, areas, auras, movimento,
acoes/reacoes, concentracao, invocacoes, condicoes e duracoes por turno nao foram
executados pelo site. O contrato de AST e dispatcher generico foi registrado em
`../bonfire-vtt/docs/TAG_RUNTIME_CONTRACT.md`, incluindo ordem, escopo, relacoes entre
fonte/alvo/sujeito e testes contratuais. O VTT nao deve criar branches por slug ou nome
de conteudo.

## Restore para producao

- Arquivo: `ref/backups/restore_consolidado_auditoria_tags_20260819.json`.
- Relatorio tecnico: `ref/backups/restore_consolidado_auditoria_tags_20260819.report.json`.
- Base comparada: `backup_completo_20260817_235225.json`.
- Registros serializados e desserializados: 5.103.
- SHA-256: `8200fa35c3120f9deb72bbeba0dfccd4ff009ca4426a389cbf381514211f9445`.
- A simulacao transacional confirmou preservacao de memoria, mapa/wiki da producao e
  conteudo comunitario. O restore deve ser aplicado pela acao `merge_conteudo` do
  console administrativo.

Restore atualizado apos a implementacao fora de combate:

- arquivo: `ref/backups/restore_consolidado_motor_nao_combate_20260820.json`;
- relatorio: `ref/backups/restore_consolidado_motor_nao_combate_20260820.report.json`;
- base: `backup_completo_20260817_235225.json`;
- registros: 5.103;
- SHA-256: `cd459416d79861a1e987e03afacdcef753b98849c8104b2faf002ecd0aaa13cc`;
- validacao do exportador: `bom=true`, memoria, mundo/mapa e conteudo comunitario
  preservados.
