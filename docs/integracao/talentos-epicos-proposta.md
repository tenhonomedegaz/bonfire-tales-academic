# Talentos épicos: proposta para decisão após V3-DEV

**Estado:** revisão de staging; sem aprovação para importação ou publicação. O catálogo de referência desta frente é [talentos-epicos-staging.json](talentos-epicos-staging.json). A decisão do PO ocorre somente após V3-DEV.

## O que está confirmado

- O staging contém **31 títulos únicos**: Combate 7, Conjuração 4, Exploração 5, Sobrevivência 9, Social 2, Suporte 2 e Utilidade 2. Cada entrada traz título, categoria, referência de seção/linha, descrição e a frase literal de aumento de atributo. As sete âncoras identificam seções, não IDs individuais de talentos.
- A introdução da seção diz **+2 em um atributo, até 22**. As 31 descrições individuais dizem **+2 em um atributo à escolha, até 30**. O staging preserva os dois textos; nenhum deles foi eleito regra prevalente.
- Dois talentos têm pré-requisito explícito: **Dádiva da Marca Arcana Superior** exige Marca Arcana Maior e Marca Potente; **Dádiva da Mente Desperta** exige Telepatia originada de Raça, Classe ou Talento. Os outros 29 não trazem pré-requisito explícito no catálogo; isso não define elegibilidade por nível, campanha ou concessão.
- Os efeitos incluem escolhas, recursos por descanso, condições e exceções. `tags_mecanicas_explicitas` é uma transcrição da frase de atributo, sem sintaxe executável do motor.
- A fonte HTML indicada no JSON está em `BonfireSite-main/ref/talentos épicos/Talentos in Bonfire Tales RPG.html` e foi consultada somente para leitura. Os 31 títulos únicos do staging aparecem como cabeçalhos no HTML; a introdução contém uma ocorrência do limite 22 e as entradas contêm 31 ocorrências de "até o máximo de 30". Esta conferência cobre títulos e conflito de teto, sem validar palavra por palavra todos os efeitos nem presumir publicação prévia de 139 talentos.

## Contrato mínimo a definir antes de implementar

| Tema | Estado atual | Proposta para especificação, sujeita ao PO |
| --- | --- | --- |
| Teto do atributo | Introdução 22; entradas 30. `TbTalento.atrib_*` é booleano de +1 por atributo. | PO fixa **um teto canônico** e a precedência textual. Só então especificar escolha de um atributo, acréscimo de +2, limite e comportamento quando o valor atual estiver próximo do teto. Manter ambos os textos no staging até a decisão. |
| Tipo e categoria | `TbTalento.tipo` aceita `origem`/`geral`; `etiqueta` já possui os sete nomes de categoria, mas não identifica raridade épica. | Definir tipo épico próprio e manter a categoria como dimensão separada. Não classificar os 31 como `geral` para caber no modelo: o Pathbuilder consulta `tipo=geral`. Não inventar IDs, slugs ou mudança de chave nesta etapa. |
| Efeitos | `descricao` comporta o texto; `tags_json` exige vocabulário do motor. | Preservar descrições completas como fonte legível. Especificar cada efeito executável com gatilho, alvo, escolha, duração, limite de uso/recarga e interação com estado da ficha; converter em tags apenas após verificar suporte real do motor. Efeitos sem suporte ficam identificados como texto, sem simular automação. |
| Pré-requisitos | `pre_requisito` é texto livre. | Representar separadamente os dois requisitos explícitos: conjunção de dois talentos para Marca Arcana Superior; origem permitida da Telepatia para Mente Desperta. Definir como validar posse e origem nos fluxos antes de habilitar seleção. Não inferir requisitos para os demais. |
| Builder e ficha | O Pathbuilder lista talentos `geral`; há consumidores de talentos por ID e descrição. | Definir quando e por quem o tipo épico pode ser concedido/selecionado, como escolhas e usos ficam persistidos, e como a ficha exibe efeitos textuais ou calculados. Cobrir criação, evolução, prévia e personagens existentes antes de expor o catálogo. |

**Decisão indispensável consolidada ao PO, após V3-DEV:** qual texto prevalece para o teto (22 ou 30), qual é a regra de elegibilidade/concessão de talentos épicos e quais efeitos precisam de automação na primeira entrega? Essas respostas liberam o contrato de tipo, atributo, requisitos e builder; esta proposta não escolhe regras conflitantes.

## Gate de aceite da próxima etapa

Registrar a decisão do PO após V3-DEV; revisar o contrato com os consumidores de `TbTalento`; então planejar modelo, migração, motor, builder e testes regionais em frente própria. Não importar estes 31 registros nem publicar em produção com base apenas neste documento.
