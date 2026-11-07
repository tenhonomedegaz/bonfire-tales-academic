# Importacao automatizada do historico de fichas do bot

## Regra vigente de cruzamento e saldo

- Nome normalizado identico, ou similaridade de pelo menos 80% com mesmo mestre
  identificado e data em ate 7 dias. Capitulos/numeros diferentes nao sao fundidos.
  Mais de uma candidata continua pendente, sem escolher a primeira.
- O log oficial comprova participacao; a quantidade prioriza o valor registrado
  no bot. Boost explicitamente declarado pode dobrar a base, sem dobrar novamente
  um valor individual que ja coincide com o relato.
- Sem quantidade, usar tempo ativo run/pause/finish e a tabela do bot. Aceitar o
  proximo marco quando faltam ate 20 minutos e o relato informa esse marco;
  nao inventar duracao nem arredondar sem essa evidencia.
- O saldo conciliado fica separado do total bruto do log. Divergencias sao
  preservadas; a conciliacao nao paga novamente nem incrementa a ficha existente.
- Missoes sem registro ou classificacao continuam pendentes. O vinculo e unico e
  pode ser consultado tanto pela fonte/personagem quanto pela missao no buscador.

## Conciliacao e comprovacao

A ferramenta separa missao jogada, salario/FGTS, Server Boost, resgate MM, troca de
Moeda de Evento e outros bonus.

**Decisao do PO:** os logs historicos cadastrados no bot sao editados e ja
aprovados pela staff. A planilha oficial, lida diretamente do link cadastrado,
comprova a participacao antiga e os lancamentos, mesmo sem jogadores no bot novo.
Esse modo fica registrado como `registered_staff_log` na previa e no recibo.
Uma missao unica encontrada pelo titulo pode ser vinculada usando essa evidencia;
quantidades divergentes ficam destacadas e o saldo segue a precedencia acima, sem sobrescrever o bot. Bonus e
resgates dessa origem ficam identificados como `Log da staff aprovado`, sem exigir
que a equipe aprove tudo novamente e sem pagar os valores uma segunda vez.

Um XLSX avulso enviado por upload **nao herda essa autoridade**, mesmo que copie
nome da ficha e mestre `Bonfire`. Nessa origem, comprovacao do bot ou revisao
explicita continuam obrigatorias. O pressuposto externo deste contrato e que o
link oficial aponta um log sob controle da staff, nao uma copia editavel apenas
pelo jogador. O importador nao consegue inspecionar permissoes do Google Drive.

Fila privada: `/gestao/historico/conciliacao/`. Acesso por Administrador ou pela
permissao especifica `home.review_character_history`, delegavel a equipe; o booleano
`is_staff` sozinho nao concede esse poder. Revisor comum nao aprova o proprio
historico. Administradores podem tratar o proprio caso com a mesma auditoria.

O detalhe da entrada oferece:

- Busca de missao concluida do bot, registro validado da planilha e historico
  atestado pela equipe, com nome, data, mestre e quantidade quando registrada.
- Vinculo explicito quando a origem avulsa nao comprovou a participacao ou o
  cruzamento ficou ambiguo, mediante
  justificativa e evidencia. Canceladas e entradas excluidas continuam recusadas.
- Registro historico de uma missao que de fato ocorreu mas nunca entrou no bot,
  com titulo, data, mestre e evidencia obrigatorios. Nao cria missao falsa no bot,
  nao credita MM e pode ser reutilizado por outros participantes da mesma mesa.
- Busca dos recibos MM e resgates da planilha do dono da ficha. Um recibo de outra
  conta ou com personagem de destino diferente nao valida o lancamento. O mesmo
  recibo nao pode justificar dois resgates independentes.
- Validacao de bonificacao com evidencia, rejeicao e reabertura, com registro de
  quem alterou, antes/depois, justificativa e referencia. Uma nova importacao que
  modifica a linha invalida a decisao anterior, sem apagar a auditoria.

Uma troca historica de Moeda de Evento de origem avulsa exige comprovacao do resgate MM associado,
da quantidade e do gasto. A fonte registrada identifica um personagem legado;
nao e necessario inventar uma ficha jogavel atual para auditar o passado. Ausencia
de comprovante nessa origem permanece pendente; o log oficial ja aprovado conta
como evidencia historica. A conciliacao nunca concede aventuras, ouro,
braseiros ou moedas: comprovar uma concessao antiga nao e paga-la de novo.

No mercado, **novas entregas** seguem outro fluxo: contrato declarativo da
recompensa, personagem do dono selecionado, carteira bloqueada e recibo atomico.
A Moeda de Evento so e consumida junto ao resgate de Aventura e Recompensa e os
braseiros seguem o motor de rank. Nao converter compras antigas em entregas novas.

### Missao ausente com MM de mestre reservado

Um Administrador pode informar Fogueira e MM explicitos ao registrar a missao
ausente. Esta via e somente para identidade sem conta/carteira ativa: cria o
lancamento do mestre e aumenta sua reserva, sem escolher um Discord suspeito nem
creditar uma conta. Repetir a mesma missao nao soma novamente. Exige backup antes
da alteracao; erro reverte missao, lancamento e saldo. O valor de MM nao determina
as aventuras do personagem. Mestres com carteira ativa exigem o fluxo financeiro
existente, nao um ajuste silencioso por este importador.

Caso autorizado: Dragonforce, 30/08/2026, F46/Mestre Ayan, 600 MM; as 12 aventuras
da ficha sao um dado separado. O pacote
`home/content_packages/master_legacy/staff-supplement-20261106.json` ainda esta
**pendente de aplicacao na producao**, nao e recibo de credito. O Ayan foi localizado
sem conta/Discord confirmado; nenhuma identidade foi presumida.

## Objetivo e acesso

Ferramenta em `/gestao/fichas-bot/`, somente para Administrador ativo
(`is_superuser`). Um ID Discord consulta todas as fichas registradas para aquele
jogador no bot. A planilha vem do cadastro existente, nao de uma URL arbitraria.

Fluxo: consultar jogador -> analisar ficha -> conferir correspondencias e
divergencias -> confirmar importacao -> recibo. A analise e o cruzamento sao
automaticos; nao exigem copiar cada aventura a mao. Uma previa nao grava dados.

Se a planilha nao permitir leitura, o mesmo fluxo aceita o XLSX exportado. O dono
e o nome do personagem continuam sendo conferidos contra o cadastro do bot.
O upload nao altera esse cadastro nem transfere propriedade.

## Dados preservados e limites

- `CharacterLogSource`: origem unica por spreadsheet, dono confirmado por Discord,
  nome e metadados, com vinculo opcional a uma ficha ja existente **do mesmo dono**.
- `CharacterLogImportBatch`: snapshot, fonte, formato, checksum, administrador e
  recibo. Exportacoes iguais com metadados ZIP diferentes nao duplicam a importacao.
- `CharacterLogMission`: associacao comprovada entre essa fonte e uma missao do bot.
  Reanalises nao duplicam o vinculo. Um vinculo que deixou de ser confirmado e
  sinalizado para revisao; o historico anterior nao e apagado silenciosamente.
- Entradas ambiguas, sem correspondencia ou avulsas sem prova permanecem no
  recibo, sem vinculo automatico. Divergencia de quantidade do bot em relacao ao
  log oficial aprovado e registrada, nao tratada como fraude do jogador.
- A importacao **nao** cria personagem jogavel, troca classe/revisao, altera nivel,
  lanca aventuras, ouro ou MM, nem muda `questPlayers` no bot. A soma ja existente
  na planilha e informacao de origem, nao uma nova concessao de progresso.
- Personagens ainda legados ficam representados como fontes de historico. A
  conversao mecanica para a ficha atual e uma operacao separada, especialmente
  quando exige escolhas do rework. Nao gerar uma ficha incompleta so para igualar
  a quantidade de personagens entre bot e site.
- Dados brutos de outros participantes nao sao publicados pelo importador. Esta
  primeira interface e privada; exposicao de historico em perfis exige respeitar
  a visibilidade da ficha vinculada.

## Formato atualmente reconhecido

Leitor Python `character_log_workbook.py`, correspondente ao formato ja usado por
`googleSheetsReader.ts` do bot. O arquivo original e somente lido.

| Origem | Dado |
| --- | --- |
| `LOG!C6` | Nome |
| `LOG!R25` | Rank |
| `LOG!T5` | Classe declarada |
| `LOG!AL6` | Nivel declarado |
| `LOG!AE7` | Total de aventuras declarado |
| `Aventuras!J3`, `J18`, `J33` e blocos seguintes de 15 linhas | Titulo da entrada |
| Rotulos Data/Data da missao, Mestre, Aventuras e Resumo dentro de cada bloco | Dados complementares, quando preenchidos |
| Rotulo Numero de Aventuras (incluindo acentos) | Quantidade explicita do bloco |
| Riqueza ganha/gasta, Boost gasto, Missao especial gasta | Evidencia declarada, sem converter moeda em progresso |

O campo `W+2` que o bot usa como marcador inicial e preservado como marcador,
nao convertido arbitrariamente em quantidade de aventuras. Valores financeiros
nao viram progresso. Formula sem resultado salvo fica desconhecida: o leitor nao
executa formulas, macros ou links externos.

Exportacoes do Google sem a dimensao da aba sao lidas com o mesmo limite de linhas;
dimensao ausente nao significa historico vazio. Um rotulo do campo vizinho nunca
e tratado como valor. Datas originais sao preservadas; divergencia dia/mes ou uma
data suspeita exige revisao, nunca troca automatica.

Limites explicitos: XLSX ate 8 MB, ZIP descompactado ate 48 MB, 6000 linhas na aba
Aventuras, 400 entradas, 2000 missoes concluidas por servidor na analise. Excesso
e recusado; nao ha truncamento silencioso de historico. Outra disposicao de
planilha precisa de um adaptador de formato, nao de regras por personagem.

## Como o cruzamento decide

1. O cadastro da ficha aponta um Discord, que deve corresponder a uma unica conta
   ativa do site. Nome de usuario parecido nao comprova propriedade.
2. Somente missoes concluidas do servidor selecionado entram como candidatas.
   Canceladas, testes excluidos, duplicatas revisadas e placeholders de importacao
   nao se tornam provas de participacao nativa.
3. O titulo usa a mesma normalizacao do portfolio: acentos/pontuacao e artigo
   inicial `The`, sem remover numeros de capitulos ou escolher o nome mais parecido.
4. O log oficial aprovado comprova a participacao do personagem legado. Para
   upload avulso, a participacao do dono precisa constar no bot e, havendo varias
   fichas para aquele Discord, exige referencia especifica de personagem.
5. Data pode desempatar candidatas, considerando inicio/agendamento e termino.
   Divergencia de data nao se transforma em pagamento ou ajuste automatico.
6. Quantidade explicita da planilha e comparada ao registro do bot. A origem
   oficial aprovada comprova participacao; a quantidade segue bot, boost ou tempo, sem alterar o bot; na
   origem avulsa, divergencia ou quantidade sem prova ficam pendentes. Entradas de
   boost/salario/token sao ajustes, nao novas missoes.
7. Mais de uma candidata comprovada ou a mesma sessao repetida na planilha fica
   ambigua. Nao escolher a primeira nem somar as linhas automaticamente.

Antes da confirmacao, dono, ficha e candidatas sao lidos novamente. Previa
alterada/expirada e recusada. Confirmacao repetida retorna o recibo existente.

## Automacao pela API existente

Mesmo segredo ja cadastrado; nenhuma nova chave e necessaria. A chave precisa
pertencer a Administrador ativo. Todos os endpoints seguem HTTPS, Bearer,
Idempotency-Key, auditoria e limites da API atual.

| Operacao POST em `/api/db/v1/operations/` | Escopo | Payload |
| --- | --- | --- |
| `character-logs-read/` | read | `discord_id`, `offset` opcional, `limit` 1..25 |
| `character-log-preview/` | read | `log_id`, `guild_id` opcional quando ha um unico servidor |
| `character-log-apply/` | write | `base_version` e `ticket` retornados pela previa |

Preview pela API busca a planilha cadastrada no servidor. O limite geral de
64 KB continua em vigor; previas muito grandes e uploads devem usar o painel.
O resultado de apply informa `rewards_credited: false` e
`playable_character_created: false`, alem do link do recibo.

## Instalacao e verificacao

### Entrega explicita de progresso historico

`character-history-delivery-preview` (read) e `character-history-delivery`
(publish, base_version) recebem `source_id`, `entry_key`, `title`, `date`,
`master_number`, `master_mm`, `mission_adventures` e `evidence`.
Restritos a chave de superusuario, fonte oficial e historico integral com
quantidades conciliadas. Criam a missao privada no banco compartilhado do bot,
reservam MM na Fogueira sem conta e vinculam personagem/participante/historico.
Nao sao endpoints de saldo livre: Fogueira, mestre, Discord, data, titulo e
quantidade precisam corresponder a fonte. Backup obrigatorio e transacao atomica.
Repeticao usa o mesmo Idempotency-Key; progresso ja existente recusa sobreposicao.

Se nao houver personagem, cria somente uma ficha-base de nivel 1 para o dono
verificado; atributos/classes/escolhas nao sao inventados a partir do historico.
As aventuras sao importadas por ledger, mas nao ha level-up, ouro ou braseiros novos
(economia do historico ja paga). O dono configura a build e faz seus level-ups.
O total conciliado pode divergir do declarado: a previa mostra ambos, mantendo
a prioridade do bot determinada pelo PO. Nao altera a planilha nem seu original.

Migration `0173_character_log_history` cria estruturas genericas de fonte,
snapshot e vinculo. Nao renumera PKs de jogadores, nao importa conteudo individual
na migration e nao escreve nas tabelas do bot. Instalar junto ao lote de codigo
pelo `/site-update` monitorado, sem comandos avulsos de banco ou novo env.

O complemento `0176_character_history_review`, depois de
`0175_master_market_delivery`, cria entradas por bloco, decisoes auditadas e
missoes historicas atestadas. As migrations nao contem dados da Andromeda nem
regras especificas de missao, mestre ou personagem.
`0177_history_master_reservation` relaciona a missao ao lancamento reservado,
tambem sem dados individuais na migration.

Cobertura local: parser, identidade, varias fichas por dono, capitulos, duplicatas,
conflitos, preview sem escrita, replay, alteracao concorrente de fonte e rollback;
fluxo HTTP com CSRF e integracao com a API. A conferencia visual usa fontes
ficticias e banco descartavel. A leitura real da planilha da Andromeda encontrou
28 entradas e 131 aventuras declaradas: 8 missoes, 4 resgates MM, 5 Server Boost,
8 salarios/FGTS e 3 bonus por tickets. O arquivo original foi somente lido; essa
contagem nao e aceite das evidencias nem importacao no banco de producao. Moedas
de Evento nao aparecem como lancamentos explicitos nessa aba e nao foram
inventadas a partir do ouro ou de suposicoes de rank.
