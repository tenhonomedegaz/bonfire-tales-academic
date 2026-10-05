# Conquistas: entrega regional da frente 10

O admin permite cadastrar `character_level` com classe principal e nível mínimo de 2 a 20. A regra usa a revisão de subida de nível e o fato canônico `character_level_up`; a classe e o nível atuais devem corresponder ao snapshot desse fato. A concessão usa `conceder_conquista`, que mantém unicidade, recompensa e notificação. Uma reversão reavalia a conta, revoga o marco automático que deixou de valer e suspende a recompensa exclusiva; concessões manuais e recompensas com outra origem ativa são preservadas.

Após criar ou ativar uma regra, a ação **Reprocessar fatos de nível para marcos selecionados** no admin avalia contas com fatos de nível anteriores. O progresso aparece somente para o dono na vitrine, e o aviso de concessão aparece somente na caixa do dono. O teste regional usa nível 2 fictício; nenhum catálogo comercial foi alterado.

Pendente de decisão do PO: equivalência Ascendido ↔ Diamante/Lenda; se “sem multiclasse” no nível 20 significa trajetória inteira ou apenas estado ao atingir o marco; limiares comerciais e artes finais. Esta entrega não ativa automaticamente conquistas dessas categorias. O reprocessamento de nível é uma ação explícita de staff e avalia todas as regras de nível ativas da conta.
