# Talentos épicos: contrato e cobertura

## Decisão do PO

- Cada talento concede +2 em um atributo escolhido, limitado a 30 apenas para esse incremento. Um valor já superior a 30 permanece intacto; bônus de outras fontes coexistem.
- Conteúdo e requisitos ficam no banco; efeitos são tags executadas pelos consumidores. Descrições permanecem em Markdown. Não criar regras por nome de talento ou classe.
- Usar o schema e a elegibilidade existentes. A etiqueta adicional exata `epico` separa esses talentos das escolhas gerais; não há aprovação para um tipo novo ou uma migração estrutural.

## Preparação da entrega

O staging [talentos-epicos-staging.json](talentos-epicos-staging.json) contém 31 definições únicas e os dois pré-requisitos textuais explícitos. A introdução da fonte menciona 22, mas o PO fixou 30 conforme as 31 entradas. O JSON de staging continua sendo referência, não publicação.

`home/epic_talent_catalog.py` valida as 31 identidades e prepara somente talentos com **todos** os efeitos adicionais conferidos no motor. `manage.py seed_epic_talents` informa a cobertura; `--apply --backup <arquivo-novo>` exige 31 candidatos completos antes de importar, faz backup dos registros anteriores, verifica colisões e usa upsert por slug. `--allow-partial-test` é aceito apenas num banco de teste isolado. A publicação em produção segue exclusivamente o fluxo autorizado.

Cobertura atual: **Visão Verdadeira** possui as tags `attr:talent_attr_score+2`, `attr_max:talent_attr_score=30` e `sense:truesight(range:120ft)`. **Erudito** usa o mesmo incremento, `prof:<perícia>` para as 18 perícias canônicas e `expertise:original_prof` para especializar apenas as proficiências prévias, inclusive de outras fontes. As outras 29 definições continuam pendentes de mapeamento e validação integral de seus efeitos; não devem ser importadas como se a descrição fosse automação. Os dois requisitos explícitos permanecem em texto até que a elegibilidade existente seja conectada e testada.

## Gate da entrega R2

Completar tags e consumidores dos 31 talentos, validar escolha, persistência, aplicação, remoção, recálculo, teto, coexistência, idempotência e requisitos. Só então integrar e enviar o lote à dev; informar o SHA no Discord para o `/site-update` do PO. Push na dev não é deploy.
