# Historico de fichas e confirmacao de nivel

## Escopo e estado

Implementacao local de ferramenta automatizada, nao reconciliacao manual dos
personagens do Gaz. Entrada: `/gestao/fichas-bot/`. Contrato completo em
`docs/character_log_import.md`. Sem escrita no banco real, commit, push ou deploy
neste marco. As demonstracoes usam SQLite descartavel e fontes ficticias.

## Arquivos e responsabilidades

| Area | Arquivos | Comportamento |
| --- | --- | --- |
| Leitura | `home/character_log_workbook.py` | Formato LOG/Aventuras do bot, download restrito, XLSX limitado, formulas somente com valor salvo |
| Cruzamento | `home/character_log_import.py` | Dono por Discord, identificacao de personagem, titulo/capitulo, data e quantidade; ambiguidades pendentes |
| Persistencia | `home/character_log_models.py`, `home/migrations/0173_character_log_history.py` | Fonte, recibo e vinculo com missao; sem premio nem nova ficha jogavel |
| Interface | `home/character_log_import_views.py`, `home/templates/home/gestao/character_logs.html`, `_character_log_rows.html`, `home/static/css/pages/character-log-import.css` | Previa sem escrita, confirmacao explicita, recibos, acesso de administrador |
| API | `home/character_log_api.py`, registro em `home/db_access_api.py` | Mesmo servico e chave existente, escopos read/write e base_version |
| Catalogo | `home/class_publication.py`, `home/class_catalog_api.py`, `home/hunter_publication_diagnostic.py`, `home/hunter_views.py`, `bonfire/settings.py`, `home/views.py` | Resolucao comum: publicacao, configuracao geral, fonte; selecao invalida nao volta silenciosamente a outra regra |
| Confirmacao de nivel | `home/views.py`, `home/static/js/subir_nivel.js` | Validacao do lote, transacao completa, recibo contra repeticao e mensagem HTTP distinta de falha de transporte |

## O que foi comprovado

- Uma resposta HTML de erro do servidor era apresentada pelo navegador como
  falha de rede. A interface agora distingue essas respostas.
- A resposta final era serializada depois do commit. Agora ela e construida
  dentro da transacao, e falha nessa etapa nao deixa progressao parcial.
- A confirmacao possui identificador preservado nas novas tentativas. O recibo
  fica na revisao de build existente; repetir a mesma intencao nao sobe outro nivel.
- Os seletores de classe divergiam entre ponteiro publicado e alias do Cacador.
  A selecao comum agora alimenta detalhe, criador, Pathbuilder, API e multiclasse,
  sem mudar os pins dos personagens existentes.
- O cenario local de nivel 4 para 5 com Revelacao Nephilim e classe legada nao
  vinculada confirma normalmente. Uma subclasse fora do snapshot fixado produz
  erro reproduzivel; nao foi comprovado que esse seja o estado real do Zariel.
- Consulta real limitada: Zariel e Paladino/Juramento da Vinganca, nivel 4,
  e nao Cacador. Sua pagina de progressao respondeu 200. A previa de nivel 5 com
  Revelacao Nephilim respondeu 200, `ready: true`, sem erros. Foi usada somente
  a rota de previa com rollback; a confirmacao real nao foi enviada e seu nivel
  nao foi alterado. Esse resultado nao encerra o incidente da confirmacao.

## O que permanece aberto

1. Instalar o lote e sua migration pelo `/site-update`, quando houver um commit
   revisado para publicacao. Nao precisa criar outra chave de API.
2. O formato real da Andromeda ja foi lido: 28 entradas, 131 aventuras. Reexecucao
   local com os candidatos lidos do banco vinculou 7 missoes e reconheceu 20 bonus/
   resgates aprovados da staff; somente Dragonforce ficou sem registro. Essa prova
   local nao aplica dados na producao nem reproduz suas decisoes de exclusao.
   Outras variantes de planilha ainda podem precisar de adaptador.
3. A previa real do Zariel passa; falta confirmar a causa do erro na rota de
   gravacao, usando seu estado/revisao e o log de erro do servidor, sem confirmar
   uma subida de nivel no lugar do dono. Nao vincular esse incidente ao Cacador
   nem declara-lo encerrado so com a melhora da mensagem.
4. O importador preserva historico e participacao comprovada. Ainda nao transforma
   a Andromeda legada em personagem jogavel atual, nao preenche escolhas mecanicas
   do rework e nao publica historico privado no perfil.
5. O Cacador ainda possui adaptadores antigos de origem, INT/SAB, regularizacao e
   mecanicas residuais. O alias `HUNTER_CREATOR_RULESET_CHECKSUM` continua aceito no
   startup por compatibilidade. Remover isso exige revisar os consumidores e dados,
   nao apagar a chave nem migrar personagens indiscriminadamente. `tags-v1` nao
   foi ativado nesta entrega. O rework integral nao tem novo aceite de producao.

## Evidencias locais

- 16 testes do importador: identidade, parser, ambiguidades, varias fichas por
  Discord, conflitos, replay, rollback, CSRF e contrato da API.
- Fluxo no navegador em 1440 e 390 px: busca, previa, confirmacao e recibo; sem
  erro JavaScript, imagem visivel quebrada ou transbordamento horizontal.
- Modelos e migrations consistentes: `makemigrations --check --dry-run` sem
  alteracoes pendentes em SQLite isolado.
- Testes focados de selecao de catalogo, consumidores principais e confirmacao de
  nivel, incluindo preservacao de personagens legados. Nao houve suite geral nem
  QA de producao.

Capturas privadas: `%LOCALAPPDATA%/BonfireQA/character-log-import-20261106/`.
Previa local descartavel: `http://127.0.0.1:8777/gestao/fichas-bot/`.

## Complemento da conciliacao

Fila `/gestao/historico/conciliacao/`, com permissao propria, busca de missoes e
recibos, sugestoes extraidas da importacao, registros historicos e auditoria.
Os logs oficiais cadastrados e aprovados pela staff comprovam participacao antiga,
sem exigir jogadores no bot novo. Upload avulso nao recebe essa confianca.
As migrations 0175-0177 adicionam entrega declarativa no mercado, fila/auditoria
e reserva de MM para Fogueira sem conta; nenhuma inclui uma regra por personagem.
O pacote autorizado de Dragonforce/F46/600 MM esta preparado, nao aplicado na
producao. Nao confundir 600 MM do mestre com 12 aventuras da ficha.
Capturas da fila: `%LOCALAPPDATA%/BonfireQA/character-history-review-20261106/`.

## QA posterior a importacao da Andromeda - pendencias abertas

Relatos do PO em 06/11/2026, com oito capturas anexadas nesta conversa.
Escopo atual: apenas registrar; nenhuma investigacao, correcao, alteracao de saldo
ou deploy autorizado nesta etapa. Sintomas abaixo sao relatos, nao causas comprovadas.
As referencias de arquivos sao pontos iniciais para investigacao futura.

Nota de estado: a entrega posterior pela API criou Dragonforce no bot e a
ficha-base 2789, com 28 lancamentos e 130 aventuras conciliadas. Portanto, a
anotacao anterior de Dragonforce "nao aplicado" descreve uma etapa ja superada.
Essa entrega nao importou ouro/braseiros nem a build mecanica. O PO relata que
o ouro deveria ser calculado; definir a conciliacao historica sem pagamento em
duplicidade, distinguindo valor historico exibido de saldo efetivamente devido.

| ID | Relato / resultado esperado | Pontos iniciais |
| --- | --- | --- |
| QA-IMP-01 | Ficha importada exigiu confirmar nivel 1 para nivel 1, sem escolhas, antes de permitir Refazer do zero. Deve iniciar diretamente a configuracao/recriacao do nivel 1. | `home/character_history_delivery_api.py`, `home/character_history.py`, `home/views.py`, `home/static/js/subir_nivel.js` |
| QA-BUILD-01 | Nao foi possivel selecionar Especializacao em Percepcao; conferir elegibilidade, proficiencia preexistente e disponibilizacao da escolha. | `home/views.py`, `home/character_engine.py`, opcoes/tags do catalogo |
| QA-BUILD-02 | Segredos de Cacador parecem continuar no conjunto antigo; conferir revisao efetiva da ficha e conclusao do rework sem sobrescrever personagens legados. | `home/class_publication.py`, `home/hunter_views.py`, catalogos/revisoes de classe |
| QA-BUILD-03 | Descricoes e opcoes do level-up mostram Markdown cru (`**`, `*`, referencias), texto corrido/truncado e pouca diferenciacao visual. Usar o leitor Markdown compartilhado e escolhas com detalhes legiveis e destaque perceptivel de selecao/alteracao. | `home/static/js/subir_nivel.js`, `home/templates/home/pages/subir_nivel.html`, leitor Markdown compartilhado |
| QA-BUILD-04 | Selecionar multiclasse nao resolve suas escolhas no mesmo lote e deixa a resolucao para o proximo level-up. Escolhas, ganhos e previa devem refletir imediatamente a classe escolhida, sem exigir outro nivel. | `home/views.py`, `home/static/js/subir_nivel.js`, fluxo de multiclasse e previa |
| QA-BUILD-05 | Lista de manobras e um dropdown extenso e pouco legivel; PO suspeita ter selecionado manobras inelegiveis. Conferir filtros e validacao no servidor, inclusive niveis de classe, subclasses e escolhas do proprio lote. Suspeita ainda nao reproduzida. | `home/static/js/subir_nivel.js`, `home/views.py`, catalogo de opcoes/tags |
| QA-BUILD-06 | Talentos raciais sem pre-requisitos aparecem como selecionaveis. Filtrar e validar raca, linhagem/essencia, talentos anteriores e nivel correto, incluindo escolhas ainda no lote. | `home/views.py`, `home/character_engine.py`, pre-requisitos/tags dos talentos |
| QA-CONTENT-01 | Olhos da Verdade Primordial referencia a magia Visao Verdadeira, mas deve referenciar o sentido Visao Verdadeira. Corrigir o tipo/alvo da referencia de dados, sem condicional por talento no motor. | descricao/tags do talento no banco, catalogo de sentidos e resolvedor de referencias Markdown |
| QA-BUILD-07 | Distribuicao de atributos por dois dropdowns `+1` e pouco intuitiva, inclusive para aumentar o mesmo atributo em +2. Reorganizar escolha e deixar saldo distribuivel, limites e previa claros. | `home/static/js/subir_nivel.js`, `home/templates/home/pages/subir_nivel.html` |
| QA-IMP-02 | Historico exibiu 0 PO em todos os lancamentos; PO espera calculo automatico. Conciliar regras e riqueza ja paga, mantendo trilha e evitando novo credito duplicado. | `home/character_history_delivery_api.py`, `home/character_engine.py`, ledger de aventuras e transacoes |
| QA-IMP-03 | Datas aparecem como `(legado)` mesmo quando a fonte tem data. Preservar/preencher `data_missao` e apresentar a data conhecida, sem inventar horario ou corrigir ambiguidades silenciosamente. | `home/character_history_delivery_api.py`, `home/character_log_workbook.py`, exibicao do historico |
| QA-IMP-04 | Resgates de Moedas de Mestre nao aparecem corretamente como resgate MM e mostram mestre `(legado)`. Distinguir origem/resgate de mesa jogada; vincular recibos quando disponiveis sem novo debito ou credito automatico. | `home/character_history_delivery_api.py`, `home/character_log_review.py`, templates do historico |
| QA-IMP-05 | Mesas reconhecidas ainda nao exibem o mestre e numero da Fogueira, mesmo com missao vinculada. Resolver identidade pelo vinculo comprovado, inclusive Fogueira com Discord e sem conta no site; nao depender exclusivamente de `id_mestre` apontar para auth.User. | `home/master_roster.py`, `home/character_log_review.py`, `home/character_history_delivery_api.py`, templates do historico |
| QA-BUILD-08 | Aba Tracos de raca/linhagem mostra descricao de lore da linhagem e apenas tracos base; faltam skills da linhagem. Exemplo Lunareth: Sinal Lunar, Bruma Serenante e Sopro Selenico. Separar lore de tracos e exibir habilidades base + linhagem/essencia selecionada. | criador de ficha, dados de tracos raciais e componentes de previa |

### Regra confirmada pelo PO

Talentos raciais NAO substituem talentos de classe: sao uma pool separada.
O personagem pode escolher talentos da raca base e da linhagem OU essencia,
respeitando os pre-requisitos. Texto antigo do catalogo que afirme substituicao
de talentos de classe deve ser tratado como inconsistencia editorial, nao como
regra para implementar ou recomendar builds.

Evidencias: imagens `codex-clipboard-cff58acd-33ff-4971-af54-7046165ca4fd.png`
ate `codex-clipboard-ee2687b2-5f62-40af-ad69-2419c0df3f56.png`, anexadas no chat;
para a previa racial, `codex-clipboard-7038a44e-e694-4a00-840a-a6b597bd6869.png`.
Os anexos nao foram copiados para o Git. Nao iniciar implementacao com base neste
registro sem nova solicitacao do PO.
