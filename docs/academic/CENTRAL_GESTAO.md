# Central de Gestao e Revisao de Historias

## Proveniencia

Marco publico de 09/11/2026, baseado na dev operacional
`b9920a3343f7909cc74815e2a4a8fb0d6718f32e`. Historico Git independente e
exclusoes do snapshot mantidos. Esta documentacao descreve implementacao e
limites conhecidos, nao resultados de pesquisa de usabilidade ou aceite em producao.

## Arquitetura e Pontos de Entrada

| Dominio | Arquivos | Contrato |
| --- | --- | --- |
| Portal | `home/gestao/views.py`, `urls.py`, templates `home/gestao/` | Sessao Django existente, navegacao por tarefa e acesso por capacidade |
| Atendimento | `portal_models.py`, `gestao/requests.py`, `request_views.py`, `workflows.py` | Responsavel, comentarios, devolutiva, reenvio, versao e eventos auditados |
| Cargos | `gestao/policy.py`, `roles.py`, `role_policy.py`, `gestao_models.py` | Administrador atribui cargos/capacidades explicitamente; previa assinada, confirmacao e recibo |
| Treinamentos | `gestao/training.py`, `training_views.py`, `market_services.py` | Registrar aprendizado antigo comprovado sem nova cobranca; preservar origens e treino pago ativo |
| Dados da ficha | `gestao/character_profile.py`, `character_profile_views.py` | Lista explicita de campos narrativos, antes/depois, evidencia e confirmacao atomica; nao altera mecanicas/saldo |
| Editorial | `gestao/editorial_views.py`, `master_portfolio.py`, `master_participation.py` | Consultar fontes nativas, paginar e decidir nos contratos existentes, sem duplicar conteudo em tickets |
| Historias | `character_story_models.py`, `character_stories.py`, `gestao/story_views.py` | Rascunho, versao enviada, comentario do revisor, devolucao e reenvio |
| Importacao | `character_history.py`, `test_imported_initial_configuration.py` | Configuracao direta do nivel inicial quando o historico importado atestado permite, sem avancar nivel artificialmente |

## Historias e Devolutivas

O texto da ficha permanece em `TbPersonagem.historia`. Cada envio cria uma
`CharacterStorySubmission`, com autor, texto exato, digest, estado, horario,
revisor e parecer. Ha no maximo um envio pendente por personagem. Novo envio
substitui o pendente, preservando os anteriores. O leitor Markdown e compartilhado.

O dono salva um rascunho ou envia ao Loremaster. O revisor le a versao enviada,
aprova ou solicita ajustes; a devolucao exige comentario. O jogador recebe aviso
interno e acessa o parecer pela ficha ou por `/jogador/historias/`. Apos corrigir,
pode reenviar. Edicoes posteriores nao herdam aprovacao anterior. Mudancas de
texto/dono, versoes substituidas e ausencia de permissao bloqueiam a decisao.

Rotas principais:

- `/jogador/personagens/<pk>/historia/`: editor e ultimos envios do dono.
- `/jogador/historias/`: ultimo parecer por personagem do jogador.
- `/gestao/editorial/?source=historia`: fila autorizada.
- `/gestao/historias/<pk>/`: leitura e parecer do revisor.

Revisores usam a permissao existente `home.review_portal_historia`, configuravel
para o cargo Loremaster. O nome do cargo sozinho nao concede acesso. Nao existe
atribuicao automatica de poderes, aprovacao por nome de usuario nem notificacao
externa de Discord/email nesta etapa. Comentarios privados nao sao exibidos a
leitores comuns de ficha. Conteudo de historia nao altera classe, atributos,
aventuras, carteira, privacidade ou cosméticos.

## Persistencia e Implantacao

As migrations 0179 a 0184 adicionam recibos, atendimento, permissoes declaradas e
versoes de historias. Nao movem PKs de contas/personagens e nao aprovam historias
antigas. `is_superuser` continua sendo administrador; a retirada de outros usos
legados de `is_staff` ainda e uma pendencia. Cadastro de novos mestres segue fechado.

Implantar exige aplicar migrations antes de servir as novas rotas e configurar
explicitamente os cargos. Esta copia publica nao aciona a producao operacional.

## Evidencias e Limites

O lote operacional passou em 71 testes focados, incluindo permissao, concorrencia
observavel, idempotencia, rollback, treinamento, correcao de dados e historias.
O ciclo revisor -> devolutiva -> jogador -> correcao -> reenvio -> status na ficha
foi exercitado no navegador com dados ficticios, em desktop e mobile.

Essas verificacoes nao substituem concorrencia real no PostgreSQL nem uma suite
geral. Ha uma expectativa antiga de navegacao da vitrine publica para revisar.
Testes que leem fixtures/pacotes excluidos precisam de dados sinteticos equivalentes;
nao copiar dados reais para faze-los passar. O caso racial corrigido somente no
fixture operacional ainda requer publicacao editorial na fonte ativa.

Para orientacao externa, enviar este documento e o backlog atualizado. Solicitar
somente a funcao/arquivo afetado e um exemplo sintetico, nunca credenciais ou dumps.
