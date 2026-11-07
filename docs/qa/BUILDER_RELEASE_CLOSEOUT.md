# Fechamento finito do release DEV

## Prioridade de fechamento em 14/10/2026

Pedido vigente: entregar a candidata de QA ainda hoje, sem prometer prazo nem
dispensar integridade. Esta secao substitui pendencias editoriais e sequencias
antigas abaixo: Terreno e resistencia Inferna JA tiveram decisao do PO aplicada;
cobertura, paridade e correcoes tem evidencias registradas. Nao reabrir fontes.

1. Concluir o diagnostico dirigido dos dois erros reais do F4 interrompido.
   Clerigo ja reportou 4/4 testes regionais aprovados; conferir o resultado dos
   modulos de ficha A/B em andamento. Nao duplicar processos/testes existentes.
2. Corrigir somente causas comprovadas e validar consumidores afetados. Nao
   alterar assercoes para esconder regressao; distinguir fixture desatualizado
   de regra incorreta com fonte independente.
3. Obter resultado terminal confiavel do gate integrado (com nomes dos testes,
   log persistente e exit code). Reutilizar evidencias inalteradas; uma execucao
   interrompida nao vale como aprovada. Nao consumir rodadas so com polling nem
   reiniciar suite completa por microcorrecao. UI: concluir o fluxo essencial
   criar/salvar/reabrir/evoluir e preservar legado; screenshots iniciais nao
   provam interacao completa. Nao adicionar novos cenarios opcionais.
4. Em paralelo SOMENTE se independente: revisar pacote/staged diff, checklist
   de atualizacao e retorno, sem disputar arquivos/banco nem repetir a revisao
   ja entregue em RELEASE_READINESS_20261014.md. Integracao e escrita finais
   ficam com um dono. Nao abrir novas funcionalidades ou auditorias gerais.
5. Com bloqueadores resolvidos e evidencias suficientes, fechar integrated,
   commitar e fazer push normal dev (ja autorizado), confirmar SHA remoto e
   notificar Discord com procedimento especifico. Nao perguntar se deve seguir.
6. Separar entrega DEV de ativacao em producao: usuario atualiza servidor;
   depois compatibilidade API/dados autorizados/QA publicado. Nao aguardar QA
   externo para entregar DEV, nem declarar a meta integral concluida antes dele.

Tratar como bloqueador perda/corrupcao de dados, seguranca/permissoes, falha de
fluxo essencial ou atualizacao sem retorno seguro. Melhorias opcionais e defeitos
visuais nao impeditivos ficam documentados para QA/nova meta; nao transformar
bug funcional desconhecido em cosmetico para cumprir horario. Se o fechamento
hoje ficar inviavel, comunicar imediatamente causa, evidencia e menor acao,
sem iniciar outra sequencia generica de diagnosticos.

A exclusao/substituicao da meta e POSTERIOR a entrega e fica pendente. Preservar
historico, SHA, decisoes e backlog; nao criar outra meta nesta rodada.

Orientacao vigente do PO em 13/10/2026. Complementa a arquitetura sem declarar
concluida a meta inteira. Marco atual: builder consistente, testes finais e push
DEV; publicacao e QA de producao sao um marco posterior.

## Fila de fechamento

| ID | Entrega | Condicao de fechamento |
| --- | --- | --- |
| F1 | Terminar troca opcional de formula no level-up, ja em execucao | UI e persistencia respeitam a regra textual; limites, preparo e fichas legadas preservados; teste focado do fluxo alterado |
| F2 | Consolidar pendencias da matriz por causa | Cada linha da matriz ligada a resultado ou caso identificado por fonte/PK/versao/mecanica; nenhum alerta sem classificacao; lista residual explicita, nao apenas "continuar auditoria" |
| F3 | Corrigir lista residual e resolver fontes | Terreno, Caracteristicas Maiores e demais casos reais de F2 corrigidos/retestados ou com pergunta editorial concreta; nenhum bloqueio de paridade omitido |
| F4 | Fechar paridade e QA integrado | Matriz completa com esperado independente do motor; fluxo real de criacao, progressao/regressao, escolhas, salvar/reabrir, legados e multiclasse suportada; suite final aprovada, sem ocultar falhas |
| F5 | Entregar DEV | Diff revisado, conteudo exportado consistente com DEV, sem segredos nem alteracoes alheias; commit e push normal dev; hash remoto confirmado; instrucoes de pull/migracao/ativacao |
| F6 | Publicacao e QA | Aguardar usuario confirmar atualizacao da producao; conferir API e preview/backup antes das mutacoes autorizadas; identidades de producao prevalecem; validar dados e paginas publicadas |

## Evidencias e limites

- Baseline: `builder-page-parity-baseline-2026-10-13.json` e matriz compactada
  correspondente neste diretorio: 13.980 linhas, 699 caminhos, 13 classes e 119
  subclasses live, alem das versoes seladas. Inventario nao e aceite funcional.
- 6.711 alertas de revisao nao sao 6.711 bugs. Agrupar causas e manter vinculo
  de TODAS as linhas, sem reduzir cobertura por amostragem.
- Aproveitar `scratch/builder-choice-role-triage-765-current.json` e evidencias
  posteriores. A classificacao antiga de Formulas Mutagenicas como somente
  runtime nao basta: conhecimento/preparo persistentes ja exigiram correcao.
- Conferir diferenca entre escolha na ativacao e escolha persistente sem usar
  essa distincao como justificativa para ignorar descricao/regra contraditoria.
- Terreno: conferir os tres conflitos remanescentes contra fonte aprovada e
  catalogo; informar nomes, niveis e alternativas reais se houver ambiguidade.
- Caracteristicas Maiores (Evolucao Totemica): localizar fonte aprovada por
  consulta dirigida. Se ausente, pedir lista/regra exata, nunca inventar.
- Evidencias de estilos do Cacador, Monge, Kensei, sopro e formulas ja existem
  neste diretorio. Revalidar somente se codigo/dados/dependencias relevantes
  mudaram; nao reabrir assuntos resolvidos por causa de triagem desatualizada.

## Disciplina de execucao

1. Concluir F1 em andamento. Na proxima rodada consolidar F2 em um unico
   registro estruturado no SQLite: ID, fonte/versao, esperado, observado,
   estado, evidencia e proxima acao. Historico continua no banco, nao neste guia.
2. F3 trabalha em lotes por causa compartilhada, nao uma rodada por assercao.
   Cada rodada deve fechar casos ou identificar impedimento concreto. Nao
   abrir novas funcionalidades, refatoracoes opcionais ou outra auditoria geral.
3. Novos defeitos reais que afetem o aceite entram na mesma lista, com causa e
   impacto; melhorias opcionais ficam no backlog e nao ampliam este release.
4. Ausencia de regra exige pergunta curta com opcoes fundamentadas no Discord.
   Avancar no trabalho independente enquanto aguarda; se nada util resta,
   blocked com question concreta. Nunca perguntar apenas se deve continuar.
5. Testes focados durante F1/F3. Rodar suite geral no F4, retestar falhas e
   consumidores afetados; nao repetir suite intacta para gerar mais evidencias.
   Processo longo deve ter log/resultado terminal, sem rodadas de mero polling.
6. Mapear F2 ao criterio coverage, F3 a corrections/parity, F4 a integrated e
   F5 a dev-push da entrega atual. Preservar IDs e criterios; nao fechar por
   porcentagem historica nem trocar checklist para aparentar progresso.
7. Reportar no Discord por marco: casos fechados/restantes, bloqueio concreto,
   proximo passo. Commit/push e acao manual precisam de mensagem explicita.
8. Preservar thread/modelo atuais e trabalho local. Cisco e curriculos continuam
   pausados. Conforme PO14/10, executar em paralelo toda tarefa independente
   com dono/escopo/dependencia explicitos. Nao permitir escrita concorrente nos
   mesmos arquivos ou banco. Revisoes somente leitura podem ocorrer sobre a
   base atual; implementacoes irmas usam worktrees e base revisada. Integracao
   sequencial, sem duplicar tarefas ou refazer auditorias aprovadas.

## Dependencias da execucao noturna (PO14/10)

| Frente | Pode iniciar | Trabalho | Depende de | Saida |
| --- | --- | --- | --- | --- |
| A: fontes de classe | Agora | Consultar HTMLs ref, reconciliar versoes e corrigir apenas regras explicitas | Fonte aprovada; perguntar se contraditoria | Dados/tags e testes focados |
| B: preparacao release | Em paralelo a A | Revisao somente leitura; checklist de migracoes, QA e publicacao | Diff atual identificado, sem assumir que nao mudara | RELEASE_READINESS_20261014.md |
| C: magias Terreno | Aguardando PO | Tres decisoes de circulo, sem inferir autorizacao | Conferencia do usuario | Decisoes registradas, correcao e reteste |
| D: integracao final | Depois A/B/C | Fechar matriz e QA integrado, revisar diff | Evidencias completas e fontes decididas | Commit/push dev e hash remoto |
| E: producao | Depois D e atualizacao pelo usuario | API dados e QA publicado | Deploy confirmado e escopo autorizado | Aceite publicado |

Esta tabela representa dependencias, nao promete horarios. Enquanto C aguarda,
A e B continuam; depois de concluidos todos os caminhos independentes, registrar
perguntas concretas para a manha, sem rodadas artificiais. Nao declarar D aprovado
com conflitos pendentes. A rotina de energia e responsabilidade do Jarvis:
suspensao sem polling periodico quando aguarda resposta, ou ate reset conhecido
de cota; nunca suspender enquanto um executor ou integracao esta trabalhando.

## Restricoes de arquitetura e publicacao

Formatacao em Markdown/dados; mecanicas em tags e motor generico quando
necessario; nenhuma excecao por nome de classe. Preservar PKs, personagens,
escolhas e versoes legadas. Nao adaptar producao ao ID local. Push autorizado
na dev nao autoriza deploy automatico, pagamento, resgate ou mutacao externa
nao relacionada. Pendencias externas antigas nao impedem finalizar F1-F5,
mas bloqueios reais da paridade nao podem ser declarados aprovados.
