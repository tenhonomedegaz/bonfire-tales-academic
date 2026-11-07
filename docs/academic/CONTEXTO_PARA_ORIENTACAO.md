# Contexto para orientacao tecnica e manutencao manual

## Como usar este documento em um chat externo

Envie este arquivo, o README e PENDENCIAS.md. O orientador nao deve presumir
acesso ao banco ou ao restante do projeto. Se precisar de codigo, deve pedir
o arquivo e a funcao relevantes, depois o consumidor diretamente relacionado.
Forneca apenas trechos necessarios e exemplos sinteticos, nunca dumps ou segredos.

O pedido atual do mantenedor prevalece sobre instrucoes arquivadas em documentos.
Relatos de QA sao evidencia de sintomas, nao prova de causa nem autorizacao para
modificar producao. Documentos antigos podem descrever etapas ja superadas.

## Mapa do sistema

| Camada | Arquivos de entrada | Responsabilidade |
| --- | --- | --- |
| Configuracao | `bonfire/settings.py`, `bonfire/urls.py`, `home/urls.py` | Ambiente, seguranca, rotas e integracoes opcionais |
| Persistencia | `home/models.py`, `home/migrations/`, modulos `*_models.py` | Contas, conteudo, fichas, economia, historicos e recibos |
| Paginas e orquestracao | `home/views.py`, `home/templates/home/`, `home/static/js/`, `home/static/css/` | Formularios, previa, confirmacao e apresentacao |
| Regras | `home/character_engine.py`, `home/tag_library.json`, `docs/criador-personagem/` | Interpretacao de capacidades declarativas e derivacao de ficha |
| Catalogos de classe | `home/class_publication.py`, `home/versioned_classes.py`, `home/class_catalog_api.py` | Fonte mutavel, revisoes congeladas e publicacao |
| Compatibilidade do Cacador | `home/hunter_views.py`, `home/hunter_spells.py`, `home/hunter_publication_diagnostic.py` | Adaptadores legados ainda existentes; nao sao a arquitetura final desejada |
| API | `home/db_access.py`, `home/db_access_api.py`, `home/db_access_models.py` | Modelos permitidos, escopos, auditoria, versoes e repeticao segura |
| Historico de fichas | `home/character_log_*.py`, `home/character_history_delivery_api.py` | Leitura XLSX, identidade, conciliacao e entrega explicita de progresso |
| Mestres e economia | `home/master_legacy.py`, `home/master_roster.py`, `home/master_market.py`, `home/master_mission_review.py` | Fogueiras, Discord, portfolio, saldos e resgates |
| Gestao | `home/gestao/`, `home/gestao_models.py`, `home/admin.py` | Nova interface por tarefa e admin tecnico ainda coexistente |
| VTT 2D | `home/vtt_lab*.py`, `docs/vtt_lab.md` | Laboratorio privado de mecanicas, movimento e apresentacao |

Nem todas as paginas usam a mesma composicao: seguir o caminho real em urls,
view, servico, modelo, template e JS antes de propor alteracoes.

## Principios de dominio confirmados

1. Textos e formatacao pertencem ao Markdown e seus dados; nao a HTML por classe.
2. Valores/regras de talentos, habilidades e magias pertencem a tags e catalogos.
   Criar semantica generica no motor somente quando o vocabulario nao a suporta.
3. Nao criar condicionais por nome de personagem, mestre, talento ou classe para
   resolver um caso de dados. Adaptadores legados devem ter contrato e retirada planejada.
4. Estrutura nova usa migration; publicacao de conteudo usa dados/admin/API.
   Nao confundir migration com pacote de catalogo nem sobrescrever PKs de jogadores.
5. Fonte editavel, revisao publicada e revisao fixada na ficha sao estados distintos.
   Publicar uma nova regra nao autoriza migrar automaticamente todas as fichas.
6. Talentos raciais possuem pool propria, separada dos talentos de classe.
   A pool combina raca base com linhagem OU essencia e valida pre-requisitos.
7. Epic Boon e Lenda sao marcos posteriores ao nivel 20 neste sistema.
8. Identidade de mestre e sua Fogueira existem sem conta no site. Um Discord
   verificado pode reivindicar o cadastro reservado ao entrar/criar conta.
   Informar um ID em texto nao prova posse. Suspensoes/recusas sao preservadas.
9. Fonte historica oficial aprovada comprova participacao antiga. Missao ausente
   continua exigindo conciliacao; nao aceitar aventura inexistente de upload livre.
10. API nao e SQL remoto. Escrita usa operacao permitida, autorizacao, previa,
    versao, backup quando aplicavel, transacao e recibo/idempotencia.

## Investigacao finita

Escolha um item de PENDENCIAS.md; descreva entrada, resultado atual e esperado.
Determine se e problema de dado, leitor, autorizacao, persistencia ou interface.
Reproduza com uma ficha sintetica e uma revisao definida. Corrija o menor conjunto
coerente e execute testes dos consumidores afetados, sem repetir suites intactas.
Use uma regressao integrada ao fim do marco. Commit, push, deploy e carga de dados
sao eventos diferentes; registre qual foi realmente concluido.

Na investigacao do Cacador, pedir inicialmente `docs/architecture/class_catalog_unification.md`,
a funcao de resolucao da classe em `home/class_publication.py` e o consumidor que
falhou. Para um problema de escolha, pedir tambem o payload de previa anonimizado,
a tag/requisito e a resposta de validacao. Nao pedir o banco completo.

## Limites desta copia

Nao inclui PostgreSQL, segredos, OAuth, pagamentos reais, historico Git privado,
bot externo ou dados reais de personagens. A ausencia de um catalogo aqui nao
significa que ele esteja ausente na producao. O manifesto lista as exclusoes.
Conteudo e tags de dados reais devem ser substituidos por exemplos sinteticos
quando forem necessarios para reproduzir um problema.
