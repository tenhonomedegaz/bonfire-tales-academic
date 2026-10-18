# Redesign Bonfire: release e reversão

Fonte fixada: `BonfireSite-redesign@7289711136e340afe5a13ba397ecce978071896d`.
Base desta frente: `7e4c13b` no branch isolado `jarvis/redesign-6113ea68`.
Este guia prepara S11; a revisão final deve registrar os SHAs efetivos, lotes
G01 aprovados e resultados de S09/S10 antes do aceite de S11 ou do push S12.

## Gates de entrada

| Gate | Evidência necessária | Efeito |
| --- | --- | --- |
| G01 | Aprovação explícita do PO para cada lote A–F de [redesign-g01-proposta.md](redesign-g01-proposta.md), com aceite individual de 0153 e 0158 | Só então editar Python, contratos, estrutura ou banco do lote aprovado. |
| S09/S10 | Integração funcional, matriz completa do charbuilder, suite geral e QA visual com resultados anexados | Libera a revisão final do pacote de release. |
| G00 | Entrega predecessora reconciliada com `dev` e conteúdo local preservado | Libera integração final e push de S12. |
| G02 | PO autoriza e executa a atualização de produção | Libera o smoke S13 no site/API; push em `dev` não prova deploy. |

## Preparação de DEV

1. Registrar SHA de origem, SHA de `dev`, branch, `git status --short`, lista de
   arquivos do diff e lotes G01 aprovados. Reconciliar o trabalho da meta
   predecessora antes de integrar; não sobrescrever o branch `main`.
2. Conferir `git diff --check`, `py -3 manage.py check` e
   `py -3 manage.py makemigrations --check --dry-run` no ambiente DEV
   identificado. Verificar `migrate --plan` **antes** de executar qualquer
   migration aprovada e conferir a cadeia 0152–0160 por lote. Não apontar um
   comando de teste ou migração para produção por engano.
3. Confirmar integridade de PK/FK e obter backup PostgreSQL verificável do
   ambiente alvo antes de migrar dados. Guardar identificador, checksum,
   horário e procedimento de restauração fora do repositório. Não usar
   `loaddata` por PK para transportar catálogo entre DEV e produção; seguir
   [deploy-sync-conteudo.md](../deploy-sync-conteudo.md) somente quando houver
   lote de conteúdo aprovado.
4. Executar os testes regionais dos lotes aplicados. Em S10, executar a suite
   geral e a matriz do charbuilder, além de teclado, privacidade, pagamentos e
   screenshots nas larguras 360/390/768/1024/1440 px. Registrar comandos,
   código de saída, SHA e ambiente. Falhas ou evidências ausentes impedem S12.
5. Integrar no `dev`, revisar o diff final e publicar somente após S10/S11/G00.
   Anexar ao QA o SHA publicado, rotas de teste, contas do cofre sem expor
   credenciais, casos pendentes e instruções de reprodução.

## Reversão por tipo de alteração

| Alteração | Primeira ação | Recuperação de dados |
| --- | --- | --- |
| CSS, JS e templates | Desativar o release e restaurar o SHA anterior por novo commit revisado; preservar o histórico remoto. | Nenhuma migração de dados. |
| Rotas/serviços G01 | Retirar exposição das rotas ou flags do lote e restaurar o código compatível. | Manter dados novos até auditoria de dependências e FKs. |
| 0152, 0154–0157, 0159–0160 | Isolar escrita e exportar registros criados após o release antes de considerar reversão de schema. | Restaurar somente com plano por tabela, PK/FK conferidas e backup validado. |
| 0153 | Suspender o efeito da alteração de sintonização. | Corrigir os três itens por PK/slug a partir do backup; o `backwards` não é reversão segura após edição manual. |
| 0158 | Desativar ofertas, resgates e rotas. | Fazer operação compensatória auditável e migração corretiva específica; o `RunPython.noop` não restaura recompensas de assinatura. |
| Catálogo/conteúdo | Suspender merge e comparar prévia com produção. | Usar chaves naturais, preservando PKs de produção e memória de usuários, fichas, missões e transações. |

Na implementação local do lote D, `rollback_redesign_d_pilot` exige o inventário
pré-D e seu SHA-256. Ele fecha todas as ofertas piloto, arquiva temas sem uso e
mantém ativos os temas já adquiridos para preservar a equipagem. O resultado
separa `archived_slugs` de `retained_owned_slugs`; recibos, MM e direitos não
são apagados. A reversão de resgates MM, quando necessária, usa compensação
auditável por recibo, separada da desativação do catálogo.

Produção só é reavaliada depois da ação do PO em G02: conferir SHA servido,
respostas do site/API, login, ficha/charbuilder, mercado, anúncios e logs.
Registrar resultado de S13 separado do push e do deploy.

Para recompensas de assinatura importadas depois do inventário pré-D, capture
`preview_redesign_d_rewards --output <novo-json-absoluto>` **antes** de desativá-las.
O snapshot restrito e seu SHA-256 servem apenas a `reconcile_redesign_d_rewards`;
`rollback_redesign_d_pilot` exige o inventário completo de `preview_redesign_d`
feito no head 0154. Um snapshot só de recompensas não pode arquivar o piloto.
