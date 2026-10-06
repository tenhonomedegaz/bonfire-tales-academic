# Frente 12 — Ficha e laboratório (DEV)

Base examinada: `78fa2b9`. Aceites consultados: seções 5 e 18 da arquitetura.

## Entrega desta frente

- Q01 no laboratório: catálogo de magias fornece nome PT e EN; o seletor busca ambos sem acentos, mostra o nome EN no cartão, informa resultados e escolhas mantidas, e aceita setas e Enter. O repertório escolhido permanece visível quando o filtro não encontra resultados.
- A prévia continua transacional e sem persistência: esta entrega não altera criação, concessão de conquistas ou aplicação de level-up.
- Q09/Q10/Q12/Q13/Q14 e falhas recentes de prévia/ficha staff já tinham tratamento no código de base. Os cenários de navegador existentes passaram novamente junto ao novo cenário Q01.

## Evidência local

- `node --test home/js_tests/pathbuilder.browser.cjs` com Playwright compartilhado: 24/24.
- `home.test_pathbuilder.PathbuilderTests.test_catalogo_de_magias_inclui_nome_ingles_sem_alterar_o_nome_exibido` no PostgreSQL temporário isolado: 1/1.
- `node --check home/static/js/pathbuilder.js` e `git diff --check`: aprovados.

## Dependências de integração

- Q01 completo inclui criação, level-up, preparação e oficina via componente compartilhado fora deste escopo; os ensaios integrados desses consumidores pertencem ao integrador.
- Q05/Q11 e Q15 dependem do conteúdo e dos fluxos de criação/publicação de outras frentes. A interface desta frente não deve inventar níveis, opções ou regras exclusivas de classe para suprir essa dependência.
- Publicação comercial/editorial e diagnóstico de fichas legadas reais seguem fora deste aceite DEV local.
