# S10 — aceite local do Pathbuilder

Base: `2368953bebe375c2247724c8c5be08ba771c10d1`. Execução restrita ao
worktree da frente S10; sem produção, migração aplicada manualmente ou deploy.

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
| Caçador | 6 | pendente de revisão publicada no fixture isolado |
| Clérigo | 12 | prévia no desbloqueio e progressão 1/20 passaram |
| Druida | 7 | prévia no desbloqueio e progressão 1/20 passaram |
| Feiticeiro | 7 | prévia no desbloqueio e progressão 1/20 passaram |
| Guerreiro | 10 | prévia no desbloqueio e progressão 1/20 passaram |
| Ladino | 8 | prévia no desbloqueio e progressão 1/20 passaram |
| Mago | 13 | prévia no desbloqueio e progressão 1/20 passaram |
| Místico | 8 | prévia no desbloqueio e progressão 1/20 passaram |
| Monge | 10 | prévia no desbloqueio e progressão 1/20 passaram |
| Paladino | 9 | prévia no desbloqueio e progressão 1/20 passaram |

Total: 13 classes e 111 subclasses no catálogo; 12 classes e 105 subclasses
exercitadas ponta a ponta. Os seis casos do Caçador não contam como aceitos.

## Interface e privacidade

- Personagens existentes de dois usuários não aparecem no HTML do laboratório
  nem na ficha simulada; seus registros permanecem iguais após a prévia. O teste
  usa personagens sintéticos no banco isolado e não acessa dados de produção.
- O texto da interface informa o armazenamento no navegador e o envio da base
  e da build ao servidor para a prévia, sem criação de personagem.
- Enter e Espaço ativam etapas; `aria-current="step"` acompanha a etapa ativa.
  Em navegador real, editor, controles e ficha couberam em 360, 390, 768,
  1024 e 1440 px, sem rolagem horizontal global.

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
| `py -3.14 manage.py test home --keepdb --failfast` | 46 executados de 2265 descobertos; 1 falha em `home.test_admin_navigation.AdminNavigationTests.test_groups_cover_visible_models_once_in_stable_task_order` |

Os comandos Django usaram `DB_ENGINE=postgresql`, porta `55479` e cluster
temporário exclusivo da S10. Os testes de navegador usaram Chromium local.
A suíte geral não passou: `MODEL_GROUP` não contém `TbAutorizacaoVitrine`,
`TbFeitoLenda` e `TbVerificacaoMesa`, esperados pelo teste em arquivo fora do
escopo S10. Nenhum aceite geral é declarado com essa falha.

## Limites do aceite

- O handoff `redesign-s09-handoff.md` descreve integrações pendentes, mas não
  registra um aceite S09. A dependência S09 aceita permanece sem evidência
  nesta frente.
- G01 não foi alterado. G00 permanece reservado à S12 e G02 à produção.
- A matriz não substitui uma auditoria de personagens reais nem valida o
  Caçador sem revisão publicada. Essas verificações dependem de outra frente.
