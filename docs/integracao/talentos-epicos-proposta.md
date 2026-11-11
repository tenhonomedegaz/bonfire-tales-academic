# Talentos épicos: contrato e cobertura

## Decisão do PO

- Cada talento concede +2 em um atributo escolhido, limitado a 30 apenas para esse incremento. Um valor já superior a 30 permanece intacto; bônus de outras fontes coexistem.
- Conteúdo e requisitos ficam no banco; efeitos são tags executadas pelos consumidores. Descrições permanecem em Markdown. Não criar regras por nome de talento ou classe.
- Usar o schema e a elegibilidade existentes. A etiqueta adicional exata `epico` separa esses talentos das escolhas gerais; não há aprovação para um tipo novo ou uma migração estrutural.

## Preparação da entrega

O staging [talentos-epicos-staging.json](talentos-epicos-staging.json) contém 31 definições únicas e os dois pré-requisitos textuais explícitos. A introdução da fonte menciona 22, mas o PO fixou 30 conforme as 31 entradas. O JSON de staging continua sendo referência, não publicação.

`home/epic_talent_catalog.py` valida as 31 identidades e prepara somente talentos com **todos** os efeitos adicionais conferidos no motor. `manage.py seed_epic_talents` informa a cobertura; `--apply --backup <arquivo-novo>` exige 31 candidatos completos antes de importar, faz backup dos registros anteriores, verifica colisões e usa upsert por slug. `--allow-partial-test` é aceito apenas num banco de teste isolado. A publicação em produção segue exclusivamente o fluxo autorizado.

Cobertura atual: **Visão Verdadeira** possui as tags `attr:talent_attr_score+2`, `attr_max:talent_attr_score=30` e `sense:truesight(range:120ft)`. **Erudito** usa o mesmo incremento, `prof:<perícia>` para as 18 perícias canônicas e `expertise:original_prof` para especializar apenas as proficiências prévias, inclusive de outras fontes. **Resiliência Sangrenta** usa a condição `requires:self{sangrando}` e as 12 resistências explícitas da fonte; a ficha reavalia essas tags com PV atuais e máximo calculado. **Fortitude** soma 40 PV máximos e concede cura adicional igual ao modificador de Constituição uma vez até o início do próximo turno no consumidor de encontros. As outras 27 definições continuam pendentes de mapeamento e validação integral de seus efeitos; não devem ser importadas como se a descrição fosse automação.

O avaliador geral reconhece a conjunção `e` do requisito de **Marca Arcana Superior**, mas a fonte exige "Marca Arcana Maior" e o catálogo atual contém "Marca Arcana Superior" e "Marca Potente". Nenhuma equivalência entre Maior e Superior foi presumida. O requisito de Telepatia de **Mente Desperta** confere tags passivas originadas de Raça, Classe ou Talento; item ou efeito temporário não o satisfaz.

**Tempestade** tem resistência a raio e trovejante e imunidade a ambos enquanto Sangrando verificadas no consumidor de dano tipado. As tags constam de `PARTIAL_EFFECTS` e não entram na carga: a desvantagem nos testes de resistência contra magias desses tipos ainda não tem consumidor de conjuração comprovado. A fonte não define um nível de aquisição automática para os épicos; nenhum nível foi presumido.

**Dádiva do Domínio do Céu** tem voo com pairar na ficha e *Caminhar no Vento* concedido sem espaço nem componentes, uma vez por descanso longo. A ficha expõe o limite de queda de 60 pés por turno após os primeiros 5 pés; o motor de encontro consome a regra por tags e compartilha o limite entre quedas no mesmo turno. A busca de chamadas em `home/` não encontrou uso do motor de encontro pelo site. A entrada volta a `PARTIAL_EFFECTS` até existir um consumidor no fluxo real; o aceite anterior de 5/31 candidatos era prematuro.

**Saúde Abundante** tem o acréscimo de 5 PV temporários implementado no motor de encontro, com absorção de dano e substituição do valor anterior; faltam a recuperação máxima por Dados de Vida e o fluxo real do site. **Velocidade** tem +30 pés e imunidade a Paralisado/Restringido na ficha; a concessão inata de *Velocidade* compila sem espaço ou componentes e com descanso curto/longo, mas o encerramento sem letargia e a saída de Agarrado não têm consumidor comprovado. Ambas permanecem em `PARTIAL_EFFECTS`.

## Gate da entrega R2

Completar tags e consumidores dos 31 talentos, validar escolha, persistência, aplicação, remoção, recálculo, teto, coexistência, idempotência e requisitos. Só então integrar e enviar o lote à dev; informar o SHA no Discord para o `/site-update` do PO. Push na dev não é deploy.
