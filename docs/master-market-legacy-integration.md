# Mercado de mestres: identidade, historico e moedas legadas

## Resgate atual para personagem

`0175_master_market_delivery` e somente estrutural: nao converte catalogo, saldos
nem recibos legados. `TbRecompensaMestre.efeito=aventura_recompensa` declara o
contrato de uma aventura e ouro de progressao por unidade; o padrao `manual`
preserva o cumprimento pela staff. A ativacao precisa identificar a oferta por
seu ID e aprovar esse contrato explicitamente, nunca pelo nome ou descricao.

Ativacao pelo cadastro existente (nao executada nesta entrega): depois da migration,
abrir `/admin/home/tbrecompensamestre/<ID>/change/` da oferta conferida, manter
tipo `normal`, selecionar **Efeito: Uma aventura e ouro de progressao por unidade**
e salvar. O campo esta no formulario padrao; a listagem exibe e filtra o efeito.
O admin exige a permissao existente de editar recompensas e mantem seu historico
de alteracoes. Nao e necessario criar outro produto nem localizar a oferta pelo
nome em runtime. Preco, slug e demais dados do produto nao sao substituidos.

O resgate exige personagem ativo do dono por ID e token assinado com preco e
efeito. `usar_moedas_evento=on` consome uma moeda por unidade, junto com as MM,
e concede os braseiros correspondentes. Sem essa opcao, nao consome moedas nem
concede braseiros. Ouro e braseiros usam o motor de progressao existente, com
o rank anterior a cada aventura, inclusive em lotes que cruzam ranks. Nao sobe
automaticamente nivel de classe nem fabrica uma mesa jogada ou conquista.

O motor distingue rank de progressao (`derive()['progressao']['rank']`, vindo
de `nivel_por_aventuras`) do BP de classe (`derive()['bonus_proficiencia']`, vindo
dos niveis de classe ja aplicados). Este contrato segue o rank de progressao,
como `aplicar_aventuras`; nao usa o BP de classe atrasado nem antecipa o rank
posterior ao resgate. Marco: personagem nivel 4 com 8 aventuras recebe, num lote
de duas unidades com evento, 2 + 3 Braseiros. A primeira aventura cruza 9 mas paga
Obsidiana; a segunda ja paga Ametista. Com 9 aventuras e nivel ainda 4, cada
unidade paga Ametista (3), nao o BP de classe (2). O recibo registra os ranks
usados e o nivel do personagem separadamente. Nao altera a regra de ouro.

Carteira, personagem, ledger de aventuras (origem `mercado_mestre`), carteira de
ouro e recibo de MM sao gravados na mesma transacao. O recibo preserva IDs do
destino/oferta, quantidade, operacao unica, moedas consumidas, niveis usados,
ouro em PC, braseiros e IDs dos lancamentos. Repeticao nao entrega novamente;
mudar destino, quantidade ou opcao de evento na mesma operacao e recusado.
A rota antiga de conversao isolada permanece com o mesmo URL, mas sem debito
ou entrega: exige resgate conjunto.

Recibos legados opacos ficam intactos. Um replay legado nao pode ser usado para
inventar destino, bonus, debito de evento ou nova entrega. Havendo tentativa de
vincular esses efeitos a um recibo antigo, retorna `conciliacao` sem alteracao
financeira. A comprovacao auditada dessa conciliacao e um fluxo separado; nao
ha credito automatico por texto, saldo importado ou entrada de historico.

## Origem e alcance

Fonte: copia `Mercado de Mestres.xlsx` fornecida pelo PO, extraida sem modificar o arquivo.
O link Google Sheets nao ficou acessivel nesta sessao. A copia nao e uma sincronizacao
continua com o Drive nem comprova alteracoes posteriores na planilha online.

Checksum SHA-256 do XLSX: `80140b365645879bec6f75ff5ab8bef6b76d9dbcb158423293c611c43faf9640`.

- 74 identidades de mestre, com numero da Fogueira e nome original.
- 778 lancamentos validos: 448 aventuras e 330 resgates.
- Seis lancamentos em quarentena, preservados integralmente no arquivo de origem arquivado.
- Cinco diferencas entre totais CALCs e lancamentos aceitos, preservadas como avisos.
- As definicoes antigas das dez recompensas tambem ficam arquivadas. Nao sobrescrevem
  automaticamente o catalogo atual com precos/regras legadas.

O pacote e dado, nao migration de conteudo nem script SQL:
`home/content_packages/master_legacy/mercado-mestres-20261104.json`.
A migration `0168_master_legacy_import` cria somente as tres tabelas genericas do fluxo.

## Identidades e vinculos

`TbMestreLegado` preserva numero, nome e saldos antes de existir uma conta.
Seu campo `user` pode apontar para qualquer conta autorizada, independentemente do login.
Por exemplo, Mestra Hani pode ser atribuida a `leehani17`. Isso e um vinculo de dados,
nao uma condicional especifica para Hani ou Gaz no codigo.

Uma Fogueira identifica o cadastro legado do mestre, nao uma missao individual.
`TbRegistroMestreLegado.bot_quest_id` identifica a missao do bot quando comprovada.
Registros sem correspondencia continuam validos e consultaveis; nao se apagam registros
porque a missao antiga foi removida do bot.

## Conferencia da autoria

O bot grava normalmente IDs Discord em `questMaster` e `createdBy`.
A mensagem publicada e enviada pelo bot; seu autor Discord nao prova quem mestrou.
A conferencia usa as publicacoes armazenadas em `rpg_quests`, nao varre conversas privadas.

1. Considerar publicacoes e missoes em execucao/pausadas/congeladas/finalizadas.
2. Ligar aventuras por titulo normalizado e data exata. Correspondencia repetida ou
   disputada por dois mestres nao e atribuida automaticamente.
   O DateTime UTC sem fuso do Prisma e interpretado como UTC antes da conversao
   para o dia brasileiro (`America/Sao_Paulo`, configuravel por `MASTER_LEGACY_TIME_ZONE`).
   Isso nao altera o valor guardado pelo bot nem depende do fuso do servidor Django.
3. Verificar tambem as demais publicacoes do candidato mestre no banco.
4. Exigir cobertura de todas as aventuras importadas, sem aventuras em quarentena,
   autores desconhecidos ou divergencia entre ID do mestre e ID de quem publicou.
5. Mais de um servidor Discord exige `guild_id` explicito. Mais de 20000 publicacoes
   recusa a operacao em vez de concluir com uma amostra.
6. Guardar contagens, autores e resultado da evidencia. Ausencia de evidencia nao e aprovacao.

Se o ID for inequivoco, uma conta existente com Discord verificado recebe o vinculo.
Sem conta existente, o ID fica reservado na identidade; ao vincular esse Discord por
OAuth posteriormente, a conta reivindica o cadastro e recebe a autorizacao de mestre.
Uma suspensao/recusa administrativa nao e desfeita por essa rotina.
Nao sao atribuidos cargos no servidor Discord por este recurso.

## Carteira e direitos

- Carteira vazia, sem historico previo: importar lancamentos uma vez e conciliar para
  o saldo declarado no Bau. O ajuste fica explicito no ledger.
- Moedas de Evento sao o saldo da planilha. Nao gerar moedas novamente pelas aventuras antigas.
- Carteira existente: vincular a identidade, mas deixar moedas pendentes. Um superusuario
  escolhe somar ou substituir depois de verificar sobreposicao e os saldos atuais.
- Repetir arquivo, vinculo ou login nao duplica historico ou moedas.
- Nao reatribuir uma identidade ja vinculada a outra conta automaticamente.
- Uma primeira compra comprovada de Mestre Ouro concede direito permanente. Mensalidades
  antigas permanecem como historico; nao existe cobranca recorrente criada pela importacao.
  Historico ambiguo de Mestre Ouro fica para revisao. O cofre nao volta ao catalogo.
- A lista antiga de produtos nao substitui a politica atual de slots nem implementa a
  formula de preco de Rebuild por nivel. Esse item continua dependendo da regra atual.

## Administracao

Somente superusuarios ativos podem importar/atribuir/conciliar por estas telas:

- `/admin/home/tbimportacaomestre/`: importar XLSX com previa e confirmacao assinada.
- `/admin/home/tbmestrelegado/`: pesquisar por Fogueira, nome ou login, usar
  **Vincular / conciliar** e conferir autoria no bot pela acao de lote.
- `/admin/home/tbregistromestrelegado/`: consultar todos os registros, origem e ID do bot.

Importar a fonte ou o mesmo arquivo novamente e seguro. Uma planilha diferente para uma
fonte ja importada exige conciliacao, nao soma automatica. Os dados antigos ficam preservados.

## API e ativacao

Depois do deploy pelo `/site-update`, com a migration aplicada, usar as operacoes existentes
de `/api/db/v1/operations/<nome>/`, sempre HTTPS + Bearer + Idempotency-Key:

| Operacao | Escopo | Corpo |
| --- | --- | --- |
| `master-legacy-preview` | read | `package`, `source_sha256` |
| `master-legacy-import` | publish | mesmo corpo da previa |
| `master-legacy-discover` | publish | `import_id`, `guild_id` opcional |
| `master-legacy-report` | read | `import_id`, `offset`, `limit` (1..50) |
| `master-legacy-bind` | publish, chave de superusuario ativo | `identity_id`, `username` exato, `wallet_mode` opcional |
| `master-legacy-confirm` | publish, chave de superusuario ativo | `import_id`, `source_sha256`, `confirmations` |
| `master-missions-audit` | read, chave de superusuario ativo | `import_id`, `guild_id`, `after_id` opcional, `limit` (1..50) |
| `master-legacy-bot-preview` | read, chave de superusuario ativo | `import_id`, `guild_id`, `source_sha256`, `record_keys`, `admin_validated=true` |
| `master-legacy-bot-apply` | publish, chave de superusuario ativo | mesmo corpo da previa + `base_version` |
| `master-mission-review-preview` | read, chave de superusuario ativo | `import_id`, `guild_id`, `items`, `role_names` opcional |
| `master-mission-review-apply` | publish, chave de superusuario ativo | mesmo corpo da previa + `base_version` |

Para o pacote fornecido, `package` e `mercado-mestres-20261104` e o hash e o SHA-256 acima.
Importacao e descoberta exigem backup PostgreSQL verificado no servidor. A operacao de
importacao nao cria contas nem muda carteiras: a atribuicao/descoberta e uma etapa explicita.
`bind` usa `wallet_mode=empty` por padrao. `add`/`replace` exigem `expected_balance`
e `expected_events` inteiros iguais aos saldos atuais; nunca escolher esses modos por tentativa.

### Confirmacoes manuais por Discord, inclusive sem conta

`master-legacy-confirm` recebe um lote de 1 a 100 objetos
`{"number": 40, "discord_id": "[discord-id]"}` em `confirmations`.
O numero e o da Fogueira; o ID Discord deve ser texto, nunca numero JSON.
O lote exige o checksum da fonte importada e backup verificado antes da gravacao.
Reserva o ID mesmo se o mestre saiu do servidor ou ainda nao tem conta no site.
Se uma unica conta possui esse Discord verificado, vincula a ela sem aproximar nomes.
O OAuth existente reivindica reservas futuras. Nenhuma conta artificial e criada.
O login normal tambem reconcilia reservas quando a conta ja possui Discord
vinculado. A aprovacao e o vinculo ao portfolio nao dependem do sucesso da
importacao financeira: se esta falhar, fica pendente sem retirar o acesso.
Suspensoes e recusas administrativas continuam preservadas. A regra e comum
a todas as Fogueiras, sem tratamento por nome de mestre.

Confirmacao administrativa fica auditada em `evidencia.manual_confirmation`; uma
nova descoberta automatica nao pode apaga-la por mesas ausentes ou cadastradas por
auxiliares. IDs/contas conflitantes recusam o lote inteiro, sem alteracoes parciais.
Nao ha reatribuicao silenciosa de Fogueira ja ocupada. Repetir o lote nao duplica
creditos. Carteiras existentes continuam exigindo conciliacao explicita por `bind`;
o retorno informa `reconciliation` e `wallet_imported` para separar vinculo de saldo.

### Mesas privadas validadas e auditoria de missoes

A validacao administrativa das mesas da planilha nao depende de publicacao no bot.
Seus lancamentos ja fazem parte do saldo-base importado. Nao somar os valores outra
vez quando um registro do bot for criado. Para mestre sem conta vinculada, o saldo
fica reservado na Fogueira; nao atribuir ao usuario que publicou por auxilio.

`master-legacy-bot-preview` compara as chaves de aventuras arquivadas com todas as
missoes atuais do servidor, inclusive privadas/nao publicadas. Mesmo titulo/data
com outro dono exige revisao, nunca duplicacao. A previa retorna `base_version`;
`master-legacy-bot-apply` exige essa versao, backup verificado e replay idempotente.
Nao existe entrada de titulo, valor ou SQL livre: todos os dados vem da importacao.

Registros novos ficam finalizados, privados e nao publicados, sem canal Discord,
participantes ou notificacoes. `rewardAventurasOverride=0` impede premios novos.
Nao sao fabricados eventos, inicio, fim ou duracao. Como o bot exige DateTime,
`questDate` guarda 12:00 UTC apenas como ancora da data; os metadados informam
`date_precision=day` e `time_unknown=true`. Nao e o horario real da mesa.
Sem data na fonte, nao criar registro ate esclarecer, mas preservar o credito.
Sem Discord confirmado, manter o rotulo original da Fogueira, sem adivinhar dono.

`master-missions-audit` pagina por `after_id`, inclui publicadas e privadas e informa
`source_revision` para detectar mudancas durante a coleta. Nao retorna jogadores,
descricoes privadas nem os usuarios dos eventos. `owner_state` diferencia identificado,
ID Discord sem Fogueira, dono ausente e ambiguidade. Estes dois ultimos casos nao
devem ser confundidos com uma conta que existe mas ainda nao foi vinculada no site.

Tempo ativo segue os intervalos `run` ate o proximo evento, sem contar pausas.
Eventos invalidos/fora de ordem, tempo zero/ausente, cancelamento ou missao nao
finalizada tornam o registro inviavel para novo credito. `viable_for_review=true`
apenas indica que passou esses filtros, nao autoriza nem concede moedas.
A aprovacao administrativa da planilha continua preservada como base financeira;
um legado sem duracao nao e descreditado por falta de telemetria antiga.

O cancelamento atual do bot apaga a linha de `rpg_quests` e escreve no log Discord.
O relatorio deve manter cancelamentos disponiveis e registros sem tempo, com os motivos,
mas nao pode afirmar cobertura completa de cancelamentos apagados sem consultar os logs.

### Revisoes administrativas, arredondamento e republicacoes

`TbRevisaoMissaoBot` (migration de estrutura `0169`) guarda decisoes por ID de missao,
apelido confirmado do mestre, quantidade aprovada e recibo financeiro unico. Nenhuma
regra identifica missoes pelo nome no Python; nomes, IDs e valores sao dados do lote.
Nao altera a copia imutavel do XLSX nem reescreve duracao ou recompensas ja pagas aos jogadores.

Cada item da API exige `quest_id`, `decision` e `note`. Decisoes:
`confirmed`, `settled`, `duplicate`, `no_record` e `identity`.
`confirmed`/`settled` encerram a missao e gravam `adventures` no override existente do bot.
`duplicate` exige `canonical_id` do mesmo mestre e oculta a republicacao, sem apagar o historico.
`no_record` impede novas recompensas sem apagar dados. `identity` registra somente o nome
do mestre, sem presumir que a mesa foi jogada. Tags, ranks e eventos de tempo permanecem intactos.
O campo opcional `event` confirma/remove somente a tag `evento`, preservando as demais tags;
deve ser usado apenas quando a staff confirmou essa classificacao.

Modos financeiros: `none` (sem alteracao), `settled` (ja quitado, nao pagar),
`baseline` (`legacy_key` obrigatoria, valor deve ser igual ao da planilha) e `new`.
Somente `new` credita MM e moedas de evento; reexecucao nao repaga. Sem conta verificada,
o credito fica reservado ao ID Discord e e entregue pelo OAuth posterior. Vinculo legado
manual existente pode indicar a carteira autorizada por `master_number`; divergencia com
outra conta Discord verificada recusa o lote. Recibo entregue nao pode ser modificado por
uma revisao simples. A aprovacao nao reativa mestre suspenso/recusado.

Com `master_mm` omitido em `new`, o calculo segue `questEmbeds.ts` do bot:
`adventures * 100 + min(adventures * rewardPerProgression, maxTotalReward)`.
Bonus exige exatamente um cargo permitido e a regra do rank dedicado da epoca.
`role_names` e o mapa ID/nome dos cargos lido do Discord. Rank fixado na missao tem
precedencia; sem ele, exige uma unica configuracao que cubra a data historica. Nunca
substituir pelo rank atual se a evidencia da epoca estiver ausente/ambigua.
Tag `evento` concede `floor(MM / 100)` moedas de evento, sem outra conversao cumulativa
por fora. Valores explicitos aprovados podem ser informados em `master_mm`/`event_coins`.

A previa mostra tambem registros de mesmo mestre e titulo na mesma data ou na mesma
URL de mesa, ignorando query/fragmento da URL. Isso e pista de duplicacao, nao ordem para
fundir automaticamente sessoes legitimas. Republicacoes confirmadas devem apontar para
um unico registro canonico. Um legado sintetico ligado a uma mesa nativa passa a duplicata
auditavel; o lancamento da planilha e ligado ao registro nativo, sem emitir credito novamente.
Consulta de auditoria reconhece aliases aprovados e exclui `duplicate`/`no_record` de revisao.
Administracao: `/admin/home/tbrevisaomissaobot/`, somente leitura para superusuarios.

Nao e necessario copiar o XLSX para producao: o pacote instalado permite importar pela API.
As credenciais existentes sao reutilizadas; nao colocar tokens no repositorio ou neste documento.

## Seis registros a corrigir na origem

Na aba `AVENTURAS  MERCADO`:

| Celula | Fogueira | Problema preservado |
| --- | --- | --- |
| J140 | 12 | Valor do resgate ausente |
| I247 | 03 | Data `04/072026` |
| C276 | 18 | Nome da aventura numerico (`1`) |
| I288 | 14 | Ano `0206` na data `05/09/0206` |
| I310 | 72 | Data `25/092026` |
| D350 | 46 | Data `30/60/2026` |

Nao corrigir esses dados por suposicao. A quarentena e os avisos continuam no JSON
arquivado, mesmo depois da atribuicao de uma conta a cada mestre.

## Arquivos e verificacao

- `home/master_legacy_workbook.py`: leitura limitada do XLSX, formulas/caches e quarentena.
- `home/master_legacy.py`: importacao, identidade, carteira, evidencia e OAuth.
- `home/master_legacy_api.py`: pacote permitido, backup, operacoes e relatorio paginado.
- `home/master_legacy_admin.py` e templates `admin/home/master_legacy/`: operacao manual.
- `home/models.py` / migration `0168`: armazenamento e unicidade.
- `home/views.py` / `home/permissions.py`: callback Discord, permissao e identidade no mercado.
- Testes isolados: `home.test_master_legacy --isolated`, `home.test_master_legacy_workbook`
  e regressao `home.test_master_market_quantity --isolated`.

Os testes usam SQLite em memoria, nunca o PostgreSQL do usuario ou configuracao da producao.
O vinculo efetivo das contas e os saldos reais so podem ser confirmados depois da ativacao
e da leitura da evidencia no ambiente de producao.
