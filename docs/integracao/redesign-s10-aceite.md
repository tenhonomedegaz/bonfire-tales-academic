# S10 — aceite local do Pathbuilder

Base da matriz: `b061c66`; revisão de aceite: `92bbc00`. Execução restrita ao banco PostgreSQL de teste;
sem produção, migração aplicada manualmente ou deploy.

## Matriz executada

O teste `test_matriz_real_de_classes_subclasses_e_progressao_sem_persistencia`
usa `home/fixtures/conteudo.json` em PostgreSQL temporário isolado. Para cada
classe executável verifica níveis 1 e 20; para cada subclasse executável,
verifica a prévia no nível de desbloqueio, nome e ficha. Confere que nenhuma
prévia criou `TbPersonagem`.

| Classe | Subclasses no catálogo | Situação da matriz |
| --- | ---: | --- |
| Artífice | 6 | prévia no desbloqueio e progressão 1/20 passaram |
| Bárbaro | 7 | prévia no desbloqueio e progressão 1/20 passaram |
| Bardo | 8 | prévia no desbloqueio e progressão 1/20 passaram |
| Caçador | 6 legadas no fixture; 8 na revisão canônica | prévias das 8 ordens no nível 3 e progressão 1/20 passaram com revisão publicada apenas no teste |
| Clérigo | 12 | prévia no desbloqueio e progressão 1/20 passaram |
| Druida | 7 | prévia no desbloqueio e progressão 1/20 passaram |
| Feiticeiro | 7 | prévia no desbloqueio e progressão 1/20 passaram |
| Guerreiro | 10 | prévia no desbloqueio e progressão 1/20 passaram |
| Ladino | 8 | prévia no desbloqueio e progressão 1/20 passaram |
| Mago | 13 | prévia no desbloqueio e progressão 1/20 passaram |
| Místico | 8 | prévia no desbloqueio e progressão 1/20 passaram |
| Monge | 10 | prévia no desbloqueio e progressão 1/20 passaram |
| Paladino | 9 | prévia no desbloqueio e progressão 1/20 passaram |

O fixture original contém 13 classes e 111 subclasses. A matriz geral exercitou
12 classes e 105 subclasses; ela omite o Caçador quando não há publicação.
Uma matriz separada montou, dentro da transação de teste, a revisão publicada
com as oito ordens de `home/rules/hunter_rework.json`. As seis entradas legadas
do fixture permaneceram no banco; quatro não pertencem à revisão canônica.
Esses resultados não demonstram que um catálogo de Caçador já foi publicado
no banco DEV ou em produção.

## Interface e privacidade

- Personagens existentes de dois usuários não aparecem no HTML do laboratório
  nem na ficha simulada; seus registros permanecem iguais após a prévia. O teste
  usa personagens sintéticos no banco isolado e não acessa dados de produção.
- O texto da interface informa o armazenamento no navegador e o envio da base
  e da build ao servidor para a prévia, sem criação de personagem.
- Enter e Espaço ativam etapas; `aria-current="step"` acompanha a etapa ativa.
  Em navegador real, editor, controles e ficha couberam em 360, 390, 768,
  1024 e 1440 px, sem rolagem horizontal global.
- As cinco capturas reais estão em `evidencias/s10/pathbuilder-{largura}.png`.

## Evidências locais

| Comando | Resultado |
| --- | --- |
| `py -3.14 manage.py test home.test_pathbuilder.PathbuilderContratoClienteTests home.test_pathbuilder.PathbuilderTests.test_catalogo_asi_cobre_classes_e_subclasses_sem_criar_marcos` | 5 testes, OK |
| `py -3.14 manage.py test home.test_pathbuilder.PathbuilderContratoClienteTests.test_privacidade_e_etapa_ativa_sao_explicitas home.test_pathbuilder.PathbuilderTests.test_matriz_real_de_classes_subclasses_e_progressao_sem_persistencia` | 2 testes, OK |
| `py -3.14 manage.py test home.test_pathbuilder.PathbuilderTests.test_personagens_existentes_nao_entram_na_simulacao home.test_pathbuilder_e2e.PathbuilderRealE2ETests.test_s10_teclado_e_larguras_da_matriz` | 2 testes, OK |
| `py -3.14 manage.py test home.test_pathbuilder_e2e.PathbuilderRealE2ETests.test_s10_teclado_e_larguras_da_matriz --keepdb` | 1 teste, OK após incluir a checagem de Tab |
| `py -3.14 manage.py test home.test_pathbuilder_spells --keepdb` | 10 testes, OK |
| `node --test home/js_tests/pathbuilder.browser.cjs` | 37 testes, OK |
| `node --check home/static/js/pathbuilder.js` | OK |
| `py -3.14 manage.py test home.test_hunter_public_creator.HunterPublicCreatorTests.test_s10_published_hunter_orders_preview_without_persistence --keepdb` | 1 teste OK; oito ordens canônicas, níveis 1/3/20, zero personagem criado, registros legados preservados |
| `py -3.14 manage.py test home.test_pathbuilder_e2e.PathbuilderRealE2ETests.test_s10_teclado_e_larguras_da_matriz --keepdb` | 1 teste Edge OK; cinco capturas em `evidencias/s10/` |
| `py -3.14 manage.py test home.test_class_page_options --keepdb` | 6 testes OK após corrigir duas expectativas textuais legadas |

Os comandos novos usaram `DB_ENGINE=postgresql` e o banco de teste
`test_bonfire_redesign_6113ea68`. O teste de navegador usou Edge local.
A falha anterior de `MODEL_GROUP` foi corrigida em `a6c8e4c`. A suíte geral
sobre `363bd46` terminou com 2.272 testes, uma falha, nenhum erro e 19 pulados
(`%TEMP%/bonfire-s10-363bd46.log`, 9.787,982 s). A única falha foi o teste
`home.test_commerce_review_browser`: um evento `close` atrasado limpava a
compra já aberta na revisão seguinte. O commit `92bbc00` corrigiu o frontend e
adicionou reprodução determinística; o teste afetado passou 1/1 em PostgreSQL
isolado. Os consumidores próximos `home.test_commerce_presentation` e
`home.test_cosmetic_checkout` passaram 19/20, com um teste pulado. `node --check`
em `home/static/js/commerce.js` passou. Entre a suíte geral e `92bbc00`, somente
esse JS e seu teste de navegador mudaram; os outros 2.271 desfechos da suíte
(2.252 aprovações e 19 pulados) permanecem aplicáveis. Aceite local S10 por
validação composta: a falha única foi corrigida e verificada no consumidor
afetado, enquanto a matriz funcional e visual permanece inalterada. Isto não
equivale a uma suíte geral com código de saída zero em `92bbc00`.

## Limites do aceite

- S09 foi aceita separadamente. G00 foi reconciliado localmente para S12;
  G02 permanece reservado à produção.
- A matriz não substitui auditoria de personagens reais nem publicação de
  conteúdo em DEV/produção. A revisão canônica do Caçador foi simulada somente
  no banco de teste; nenhuma alteração de G01 foi aplicada.
