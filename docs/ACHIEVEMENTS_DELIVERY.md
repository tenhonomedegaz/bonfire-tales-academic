# Conquistas: entrega regional da frente 10

O admin permite cadastrar `character_level` com classe principal e nível mínimo de 2 a 20. A regra usa a revisão de subida de nível e o fato canônico `character_level_up`; a classe e o nível atuais devem corresponder ao snapshot desse fato. A concessão usa `conceder_conquista`, que mantém unicidade, recompensa e notificação. Uma reversão reavalia a conta, revoga o marco automático que deixou de valer e suspende a recompensa exclusiva; concessões manuais e recompensas com outra origem ativa são preservadas.

Após criar ou ativar uma regra, a ação **Reprocessar fatos de nível para marcos selecionados** no admin avalia contas com fatos de nível anteriores. O progresso aparece somente para o dono na vitrine, e o aviso de concessão aparece somente na caixa do dono. O teste regional usa nível 2 fictício; nenhum catálogo comercial foi alterado.

Pendente de decisão do PO: equivalência Ascendido ↔ Diamante/Lenda; se “sem multiclasse” no nível 20 significa trajetória inteira ou apenas estado ao atingir o marco; limiares comerciais e artes finais. Esta entrega não ativa automaticamente conquistas dessas categorias. O reprocessamento de nível é uma ação explícita de staff e avalia todas as regras de nível ativas da conta.

## Revogação manual no admin

Na lista **Conquistas dos usuários**, a ação **Revogar concessões manuais selecionadas** revoga somente regras manuais. A operação é idempotente: repetir a ação não altera a concessão nem cria avisos. A conquista revogada deixa a vitrine e a caixa privada do dono; uma concessão posterior reabre o aviso existente, sem duplicá-lo. O cosmético vinculado fica suspenso somente quando foi obtido por conquista e não há outra conquista ativa com a mesma recompensa nem compra confirmada. Posse registrada por outra origem permanece ativa. Regras automáticas continuam sob a avaliação dos fatos, sem revogação manual pelo admin.

Validação DEV local: `home.test_achievement_notifications` (4 testes) e `home.test_achievement_integrated` (1 teste) em PostgreSQL temporário UTF-8, todos aprovados. Nenhuma migração foi aplicada fora do banco de teste.
