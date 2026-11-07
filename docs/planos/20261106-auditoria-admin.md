# Auditoria do admin e requisitos da nova Central de Gestao

Data: 06/11/2026. Estado: diagnostico e planejamento, sem correcao funcional aplicada.
Complementa [a arquitetura da Central](20261106-central-gestao.md).
Decisoes preservadas: remover `is_staff` efetivamente; manter `is_superuser`
como Administrador; cargos reais para a equipe; nao liberar o admin antigo inteiro.

## 1. Metodo, cobertura e limites

- Codigo de referencia: HEAD `23e6197649ec038b785abfc953a83e634cb0ff1e`.
  A leitura local nao prova, por si so, o SHA executado no servidor.
- Inventario dos **75 modelos registrados** em `admin.site._registry`, inicializado
  com SQLite em memoria, sem consultar o PostgreSQL configurado.
- Conferencia autenticada em producao de **26 telas/variantes**, em 1440 e 390 px:
  **52 observacoes** de interface. Inclui listas, detalhes de amostra, importadores,
  exportador, biblioteca de tags, chaves e console ainda bloqueado.
- Apos o login, o navegador aceitou apenas GET/HEAD. Recursos de outra origem foram
  bloqueados; fontes externas podem, portanto, ter fallback nas capturas.
- Nao houve salvamento de formularios, concessao, remocao, reprocessamento, pagamento,
  exportacao de registros, restore, leitura de env pelo console ou alteracao de cargos.
  Login cria a sessao normal; nao se afirma ausencia absoluta de escritas de sessao/log.
- Nao foram criadas contas para testar todos os cargos. Nao foram reproduzidos POSTs
  perigosos, concorrencia, perda de dados ou exploracao de permissoes em producao.
- A conta de QA usada e Administradora. Ver um campo editavel nao prova que qualquer
  cargo consiga grava-lo nem que uma gravacao invalida seria aceita pelo dominio.
- Nao foi realizada auditoria completa de acessibilidade, carga ou desempenho SQL.

Fontes reproduziveis, sem valores de campos pessoais nem segredos:

- [registry.json](../qa/admin-audit-20261106/registry.json): metadados dos 75 modelos.
- [live-ui.json](../qa/admin-audit-20261106/live-ui.json): rotas, larguras, controles,
  estados HTTP, dimensoes e textos de interface; sem corpos de registros.
- [inspect_registry.py](../qa/admin-audit-20261106/inspect_registry.py): inventario isolado.
- Capturas: `%LOCALAPPDATA%/BonfireQA/admin-audit-20261106/`, fora do Git.
  Formularios foram parcialmente desfocados. Ha nomes/identificadores visiveis em
  alguns titulos; revisar/redigir antes de compartilhar publicamente.
- Coletor de leitura no Jarvis: `scratch/audit-admin-readonly-20261106.cjs`.
  Credencial protegida pelo Windows, sem senha no script ou neste documento.

**Como ler:** os 42 achados ADM abaixo sao fatos de interface/codigo confirmados;
o impacto e a prioridade sao avaliacao de engenharia. Os oito itens R sao riscos
ou verificacoes ainda abertas. Nao somar tudo como 50 vulnerabilidades.

P0 = integridade/acesso a resolver antes de delegar escrita equivalente na Central.
P1 = fluxo necessario para a substituicao ser utilizavel. P2 = consistencia/acabamento.
Nao implica emergencia comprovada de acesso nao autorizado ao painel atual.

## 2. Resumo quantitativo

| Indicador | Resultado e interpretacao |
| --- | --- |
| Modelos registrados | 75; nao 92. As 92 opcoes da tela misturam links de ferramentas e modelos |
| Sem `search_fields` | 10; inclui consultas tecnicas, nao significa que todos precisem de busca textual |
| Com FKs em `raw_id_fields` | 15; caminho tecnico ainda necessario em varias tarefas |
| Com algum JSON no modelo | 35; nao significa 35 formularios sem assistencia ou 35 erros |
| Com `delete_selected` | 53 no nivel do modulo para Administrador; guardas por objeto podem restringir |
| Modelos do bot, `managed=False` | 7; todos com cadastro/alteracao/exclusao habilitados no metadado do admin |
| Alcance dos dois patches globais | 55/75; registros posteriores nao recebem o mesmo comportamento |
| Leituras de interface | Todas as 52 observacoes retornaram HTTP 200 |
| Overflow horizontal do documento | Nao detectado nas larguras medidas; ha rolagem interna de tabelas |
| Header no celular | 223 px na amostra; consome aproximadamente um quarto da altura de 900 px |
| Formulario de classe amostrado | 360 controles editaveis com caixa de layout, incluindo inlines; cerca de 31 mil px de documento em desktop |
| Permissoes da conta | Seletor de origem com 488 opcoes; nao sao 488 permissoes concedidas ao usuario |

**Conclusao:** o problema nao e apenas estetico. A interface foi organizada em
torno da estrutura das tabelas, com politicas divergentes e atalhos de manutencao
misturados ao trabalho operacional. Trocar CSS nao resolve esse desenho.

## 3. Achados confirmados

### Acesso, cargos e identidade

#### ADM-01 | P0 | Cargo nao abre o painel
Evidencia: `home/admin.py::_admin_superuser_only`, atribuido a `admin.site.has_permission`.
Impacto: um cargo editorial com suas Permissions continua sem acesso ao painel;
dar `is_staff` nao resolve e promover a superusuario amplia direitos demais.
Plano/aceite: politica de tarefas em `/gestao/`; cada cargo entra somente no seu
escopo. GET, POST, busca e contagens aplicam a mesma politica.

#### ADM-02 | P1 | Cargos incompletos e estreitos
Evidencia: `home/migrations/0133_editorial_groups.py`; producao mostra tres Groups.
Cria Jornalista, Staff e Loremaster para partes de jornal/cronicas; nao cria Rulesmaster.
Plano/aceite: catalogo unico de cargos e matriz de capacidades aprovada. Preservar
atribuicoes existentes; nao reescrever a migration historica para resetar membros.

#### ADM-03 | P0 | Dois caminhos diferentes para conceder acesso
Evidencia: `home/management/commands/assign_editorial_permissions.py` concede
Permissions individuais e exige `is_staff`, enquanto a migration usa Groups.
Plano/aceite: atribuir cargo por um servico; explicar permissoes herdadas e excecoes.
Converter excecoes apenas com preview e aprovacao, sem apagar concessoes silenciosamente.

#### ADM-04 | P0 | `is_staff` tem efeitos fora da tela administrativa
Evidencia: `home/permissions.py::is_staff_user`, `home/badges.py`, `home/master_hub.py`.
Afeta acesso a fichas, limites/slots, apresentacao de equipe e tarefas de mestre.
Plano/aceite: mapear cada uso para capacidade ou direito proprio; testar a equivalencia.
Remover o campo sem isso alteraria regras de produto, nao somente o login do admin.

#### ADM-05 | P1 | Editar uma conta exige compreender o Django
Evidencia: `/admin/auth/user/.../change/`, `UserAdmin`, `live-ui.json`.
Flags tecnicas, dados de login, Groups e seletor com 488 Permissions aparecem no
mesmo formulario. Acesso efetivo e origem de cada permissao nao sao explicados.
Plano/aceite: separar Identidade, Cargos, Acesso efetivo e Seguranca; mostrar
Administrador como cargo derivado de `is_superuser`, sem booleano Staff substituto.

#### ADM-06 | P0 | Remocao fisica exige migracao de identidade
Evidencia: usuario concreto em imports/FKs/sinais de `home/models.py` e consumidores;
`UserAdmin` e forms padrao dependem do modelo atual. Nao e somente retirar um checkbox.
Plano/aceite: app de conta e grafo de migrations ensaiados em base vazia e clone,
PKs/hashes/M2Ms preservados, OAuth e rollback conferidos. Detalhes na arquitetura,
secao 6. Nao executar DROP isolado nem fingir remocao com propriedade sempre verdadeira.

### Navegacao e descoberta

#### ADM-07 | P1 | Dois produtos visuais para o mesmo site
Evidencia: `home/templates/admin/base_site.html`, `home/static/css/admin/bonfire_admin.css`
versus `home/templates/home/components/header.html` e base do site.
Marca, tipografia, espacamento, conta e navegacao sao montados separadamente.
Plano/aceite: shell compartilhado com variante de gestao; titulo compacto e area de
trabalho ampla. Nao copiar o header antigo e apenas renomear Admin para Gestao.

#### ADM-08 | P1 | Ida e volta acumulam guias
Evidencia: `target="_blank"` em Ver Site no admin e entradas desktop/mobile do site.
Confirmado em todas as telas administrativas visitadas.
Plano/aceite: links internos normais na mesma guia. Modificadores do navegador
continuam livres; preview externo indicado pode abrir outra guia.

#### ADM-09 | P1 | Menu representa tabelas, nao tarefas
Evidencia: `home/admin_navigation.py`, `home/templates/admin/index.html` e sidebar.
O operador precisa decidir entre Cosmeticos, Cosmeticos dos usuarios, Conquistas,
Conquistas dos usuarios, Ofertas e Resgates para resolver uma unica solicitacao.
Plano/aceite: oito areas de trabalho da arquitetura, com jornadas por jogador ou
conteudo. Cada modelo recebe destino no inventario, sem gerar 75 novas telas CRUD.

#### ADM-10 | P1 | Busca inicial nao procura jogadores nem registros
Evidencia: `home/static/js/admin/dashboard_search.js::filterNavigation` filtra DOM
de links e nomes de modelos; nao consulta entidades. Mensagem fala em tarefas/cadastros.
Plano/aceite: distinguir busca de navegacao de busca de registros; resultados com
tipo, nome e contexto, filtrados por permissao. Buscar Gaz nao deve depender de
descobrir primeiro em qual tabela esta o cadastro.

#### ADM-11 | P2 | Primeira tela gasta espaco antes de oferecer trabalho
Evidencia: `home/templates/admin/index.html`, capturas `index-1440.png`/`index-390.png`.
Titulo, boas-vindas e texto introdutorio precedem atalhos e a lista completa de tabelas.
Plano/aceite: inicio com filas autorizadas, tarefas frequentes e ultimas acoes.
No celular, a primeira tarefa relevante deve aparecer sem atravessar um bloco de boas-vindas.

#### ADM-12 | P1 | Mistura de portugues, ingles e nomes tecnicos
Evidencia: `bonfire/settings.py::LANGUAGE_CODE='en-us'`; listas e detalhes com
Select/Change/Save/Available/Chosen; labels de modelos como `social credit entrys`.
Plano/aceite: interface PT-BR, nomes por dominio e plural revisado. Alterar idioma
com regressao de parsing/formatos, nao fazer substituicao de strings no HTML do Django.

#### ADM-13 | P1 | Datas transferem a conversao de fuso ao operador
Evidencia: `TIME_ZONE='UTC'`, formulario de suspensao com aviso de tres horas de
diferenca, datas em ingles; pagina de chaves exige ISO 8601 com fuso manualmente.
Plano/aceite: apresentar America/Sao_Paulo e fuso claro; manter armazenamento temporal
consistente. UTC nao e erro por si: nao converter dados persistidos sem necessidade.

#### ADM-14 | P1 | Cancelar perde o caminho de volta
Evidencia: JS em `home/templates/admin/base_site.html` reconstrui `listPath` somente
a partir do pathname, sem os filtros/pagina da origem. Nao ha dirty guard nesse helper.
Plano/aceite: retorno interno validado, filtros e pagina preservados, confirmacao
de descarte apenas quando houver alteracoes. Nao aceitar redirect externo arbitrario.

### Formularios, tabelas e componentes

#### ADM-15 | P1 | Celular conserva a tabela larga de escritorio
Evidencia: CSS mobile define `#result_list { min-width:640px }`; amostras de tabelas
com 6-12 colunas exigem rolagem local, com larguras de ate aproximadamente 1173 px.
Plano/aceite: priorizar nome/estado/acao, detalhes secundarios no objeto, filtros
recolhiveis e indicador de rolagem quando a comparacao realmente exigir tabela.
Rolagem local nao e bug por si; nao esconder overflow global para simular responsividade.

#### ADM-16 | P2 | Comandos pequenos e hierarquia pouco diferenciada
Evidencia: listas desktop com busca/acao menores que 44 px; tres variantes de Save
lado a lado, todas enfatizadas. O CSS mobile ja aumenta varios alvos para 44 px.
Plano/aceite: comando principal claro, alternativas no lugar apropriado e espaco
de toque consistente. Menor que 44 px nao foi classificado automaticamente como
falha WCAG: contexto, espacamento e alvo efetivo precisam ser medidos.

#### ADM-17 | P1 | Classe vira um formulario monolitico
Evidencia: `TbClasseAdmin.inlines`, `TbClassehabilidadeInline`, `live-ui.json`:
amostra com 360 controles editaveis dispostos e cerca de 31 mil px em desktop.
Plano/aceite: visao de classe com abas Base, Subclasses, Progressao, Habilidades,
Recursos e Publicacao. Editar um assunto nao envia todos os formsets do conjunto.

#### ADM-18 | P1 | Acoes antes do conteudo dominam o celular
Evidencia: `BonfireAdminMixin.save_on_top=True`; captura `class-detail-390.png`.
Historico e cinco comandos empilhados aparecem antes do primeiro campo.
Plano/aceite: uma acao Salvar contextual, alternativas secundarias; barra fixa
somente se reservar espaco e nao cobrir campos, mensagens ou foco do teclado.

#### ADM-19 | P1 | Configuracao de regra ainda exige estrutura interna
Evidencia: `fieldsets` de habilidades/itens/talentos e campos `tags_json`; 35 modelos
registrados possuem JSON. Ha assistentes pontuais, por exemplo Conquista e acesso
base de magia; nao existe editor coerente cobrindo todas as familias.
Plano/aceite: assistentes a partir do contrato generico das tags, com validacao,
referencias e previa; JSON em aba avancada. Nao criar regra Python por talento/classe.

#### ADM-20 | P1 | Atalho Markdown intercepta qualquer textarea
Evidencia: `base_site.html` escuta Ctrl/Cmd B/I/K e outros atalhos sem verificar
se o campo e Markdown; pode envolver selecao de JSON/configuracao com marcadores.
Plano/aceite: editor explicito por tipo de campo; atalhos apenas no editor certo.
Ensaio isolado deve cobrir Markdown, JSON e env sem enviar formularios reais.

#### ADM-21 | P2 | Tema e CSS mantidos por sobreposicoes globais
Evidencia: `bonfire_admin.css` redefine light/dark com a mesma paleta e forca dark;
`base_site.html` inclui a folha nos blocos responsive e extrastyle.
Plano/aceite: tokens compartilhados, uma inclusao de assets por shell e variantes
explicitas; retirar overrides do admin no corte, nao carregar ambos os sistemas.

#### ADM-22 | P0 | Null no banco vira opcional no formulario por patch
Evidencia: `_bonfire_install_nullable_optional` modifica `FormClass.base_fields`
quando `model_field.null=True`, independentemente do contrato de cada tarefa.
Plano/aceite: required/blank definidos por formulario e regra do dominio. A coluna
aceitar NULL nao decide se uma transicao de negocio pode omitir o dado.

#### ADM-23 | P1 | Comportamento depende da ordem dos registros
Evidencia: `_bonfire_patch_admin_registry()` e executado antes de registros finais
e imports de outros admins; os dois patches aparecem em 55 dos 75 modelos.
Plano/aceite: configuracao explicita e componentes comuns, sem varrer/alterar
registry na importacao. Nao resolver aplicando mais patches a todos os modelos.

### Cosmeticos, personagens, economia e bot

#### ADM-24 | P1 | Concessao de cosmetico nao e uma jornada
Evidencia: `TbUsuarioCosmeticoAdmin`, detalhe amostrado: User, Cosmetico, origem
livre e suspenso_em. **Ha autocomplete** para os dois relacionamentos; o problema
nao e ausencia completa de busca, e ausencia de contexto, previa e acao de concessao.
Plano/aceite: abrir jogador, ver inventario e direitos, escolher catalogo visual,
registrar motivo, confirmar e mostrar recibo/autor. Ja possuido nao duplica direito.

#### ADM-25 | P0 | Suspender inventario nao descreve direito efetivo
Evidencia: formulario acima versus `home/cosmetic_entitlements.py`.
Direitos pagos/permanentes e fontes de evento sao resolvidos separadamente;
editar `suspenso_em` nao equivale a revogar todas as fontes.
Plano/aceite: exibir fontes e efeito real de cada comando; revogar apenas concessao
manual autorizada, preservando compras e recompensas validas de outras origens.

#### ADM-26 | P1 | Catalogo administrativo nao mostra a aparencia do produto
Evidencia: `TbCosmeticoAdmin.list_display/fieldsets`; nome/slug/css_class/assets/JSON
sem miniatura na lista nem previa integrada equivalente ao catalogo do jogador.
Plano/aceite: thumbnail leve, categoria/aquisicao/disponibilidade e previa unica
sob demanda. Configuracao tecnica fica separada da operacao de conceder.

#### ADM-27 | P0 | Transacoes e saldo aparecem como dados comuns editaveis
Evidencia: `TbTransacaoAdmin`, `TbTransacaoMestreAdmin`, `TbAventuraMestreAdmin`,
`TbPersonagemAdmin`; detalhe de MM oferece `valor_mm` e `saldo_mm` editaveis.
Plano/aceite: ledger/recibos somente leitura; ajuste, credito e estorno sao comandos
com prova, motivo, idempotencia e transacao. Nao provar correcao financeira salvando
um formulario de ledger nem duplicar o motor existente de recompensas.

#### ADM-28 | P0 | Tabelas do bot nao estao somente leitura
Evidencia: sete `Bot*Admin` com add/change/delete habilitados no registry e sem
readonly_fields. `managed=False` controla migrations, nao permissoes de escrita.
Plano/aceite: consultas tecnicas de leitura; operacoes permitidas chamam servico
do bot/integracao. Membros, moedas, flags, jobs e KeyValueStore nao viram CRUD generico.
O comentario que diz somente leitura no arquivo nao corresponde ao registro atual.

#### ADM-29 | P0 | Protecao desigual de recibos e checkout
Evidencia: `AsaasCheckoutOrderAdmin` nao torna status readonly e permite add/delete;
`CosmeticCheckoutPurchaseAdmin` impede add, mas permite delete no nivel do modulo.
Plano/aceite: pagamento/grant historico nao pode ser fabricado ou apagado pelo
formulario. Conciliacao explicita com provedor/recibo e cancelamento como evento.
O inventario de metadados nao prova efeito de uma exclusao sobre pagamento externo.

#### ADM-30 | P0 | Revisao de personagem nao e totalmente imutavel
Evidencia: `TbPersonagemRevisaoAdmin`: snapshot e timestamps readonly, mas flags,
niveis e atores continuam editaveis; `delete_selected` permanece disponivel.
Plano/aceite: consultar revisao e comparar; reversao e comando com nova prova,
nao editar a evidencia que fundamenta progressao/conquista.

#### ADM-31 | P0 | Selecao em lote pode implicar escopo maior
Evidencia: reprocessar_compras/aventuras chama comandos de todas as regras ativas;
`LegacyMasterAdmin.conferir_bot` processa cada importacao inteira da selecao.
Os rotulos ja avisam parte desse alcance, mas a selecao de linhas sugere outro escopo.
Plano/aceite: antes de executar, mostrar selecao, escopo efetivo, contas afetadas e
operacao. Nao prometer somente estes registros se o servico reconcilia a fonte toda.

#### ADM-32 | P1 | Reprocessamentos longos ocupam a requisicao
Evidencia: `call_command(... apply=True)` e loops de conciliacao em metodos de acao;
retorno final por messages, sem identificador de trabalho/progresso nesses adaptadores.
Plano/aceite: operacao longa com recibo de execucao, estado e limites; reutilizar
fila existente quando disponivel. Timeout nao pode induzir retry financeiro cego.
Nao foi medido um timeout real nesta auditoria.

### Importacao, operacao e auditoria

#### ADM-33 | P0 | Importadores possuem contratos de confirmacao diferentes
Evidencia: importador de classe/raca/talento/opcao recebe JSON oculto via CharField
e json.loads; o importador de magias usa assinatura, validade, user_id e snapshot
sob lock. O legado de mestres tambem assina seu plano de importacao.
Plano/aceite: reutilizar o padrao mais forte: plano assinado, ator, expiracao,
fingerprint dos alvos, diff, validacao novamente e aplicacao atomica/idempotente.
Campo hidden e CSRF nao vinculam, sozinhos, a gravacao a previa anteriormente exibida.

#### ADM-34 | P0 | Console concentra poderes heterogeneos
Evidencia: `server_logs_view`, `server_logs.html`: shell, env completo, logs,
restauracao, sync e geometria no mesmo conjunto apos desbloqueio.
Ha senha adicional e TTL; nao se trata de console publico sem protecao.
Plano/aceite: separar diagnostico, importacao, segredo e manutencao destrutiva;
manter shell fora do fluxo comum e operacoes tecnicas exclusivas do Administrador.

#### ADM-35 | P0 | Historico do shell persiste comando e saida brutos
Evidencia: `_append_console_history`, `_run_admin_console_command` e seu chamador:
JSONL com comando/saida/alvo/data, sem redacao de segredos nem ator nesses campos.
Plano/aceite: nao persistir credenciais/env; registrar identidade do operador e
comando permitido com parametros redigidos. Retencao/permissoes do arquivo precisam
ser auditadas antes de preservar esse mecanismo. Nenhum historico real foi lido.

#### ADM-36 | P0 | Backup completo pode ser silenciosamente parcial
Evidencia: `download_backup_view` captura qualquer excecao por modelo e continua;
ao final retorna arquivo chamado backup_completo sem manifesto de falhas.
Plano/aceite: backup verificado, manifesto de tabelas/contagens/checksums e falha
explicita. Incluir credenciais-hash apenas no backup tecnico restrito, nunca exportacao
de catalogo. Nao foi provocado erro de banco nem baixado backup para testar isso.

#### ADM-37 | P0 | Restore completo tem menos garantias que sync novo
Evidencia: ramo `restore_backup` valida palavra de confirmacao e bloqueia fixture
somente de conteudo, mas o caminho generico faz upsert por PK sem previa/backup
verificado obrigatorio nesse ramo. Os caminhos novos de catalog_sync tem esses controles.
Plano/aceite: analisar identidade, manifestos e diff antes; backup verificado,
allowlist e rollback ensaiado. Preservar guardas existentes; nao confundir restore
com merge de conteudo nem restaurar PKs de DEV sobre jogadores da producao.

#### ADM-38 | P1 | Leitura de logs nao e limitada ao trecho solicitado
Evidencia: `_tail_file` usa `readlines()` antes de selecionar as ultimas linhas;
`_read_console_history` carrega o JSONL inteiro antes de cortar as 40 entradas.
Plano/aceite: leitura limitada e rotacao/retencao, mensagens de erro sanitizadas;
medir com arquivo representativo em DEV. Nao foi medido consumo do servidor.

#### ADM-39 | P0 | Auditoria de gestao de chave nao identifica todo operador
Evidencia: `db_access_admin.py::_audit_management` deliberadamente nao recebe ator;
DbAccessAudit nao tem campo de usuario. created_by identifica criador da chave,
nao necessariamente quem a revogou ou rotacionou depois.
Plano/aceite: registrar referencia interna ao ator e resultado sem segredo/PII
desnecessaria; nao adicionar senha nem corpo HTTP ao log em nome de rastreabilidade.

#### ADM-40 | P1 | Tela de chave pede conhecimento tecnico e omite contexto
Evidencia: `db_access_keys.html` recebe data ISO livre; metadados incluem last_used_at
e rotated_from, mas tabela nao os mostra. Estado considera so revoked_at e pode
mostrar Ativa mesmo depois de expires_at. API `is_usable()` verifica expiracao corretamente.
Plano/aceite: estado Ativa/Expirada/Revogada, data local, ultima utilizacao,
dependencias e orientacao de conexao. Explicar que rotacionar revoga imediatamente
a chave anterior. Segredo continua exibido uma vez e nunca entra na documentacao.

#### ADM-41 | P1 | Moderar mural e uma acao sem motivo estruturado
Evidencia: `profile_comments_admin.py::soft_remove_comments` atualiza removido_em/por
diretamente e mostra quantidade; nao apresenta confirmacao propria/motivo.
Plano/aceite: previa do comentario, alvo/autor, justificativa e registro de decisao;
preservar soft delete e recusas de add/delete fisico que ja existem.

#### ADM-42 | P1 | Historico da operacao esta espalhado por mecanismos
Evidencia: LogEntry do admin/exportador, DbAccessAudit, recibos de dominio,
historico JSONL do console e filas de entrega sao exibidos separadamente.
Plano/aceite: timeline por entidade/tarefa com referencias as provas existentes,
ator, motivo, versao, resultado e request ID. Nao criar segundo ledger nem afirmar
que nao ha auditoria nenhuma: ha varias fontes, mas nao uma consulta operacional coerente.

## 4. Riscos e verificacoes ainda abertos

| ID / prioridade | Evidencia/limite | Verificacao e destino |
| --- | --- | --- |
| R-01 / P0 | Link Excluir e montado com has_delete_permission(request), sem objeto | Ensaio isolado por tipo/origem; botao e POST devem respeitar o objeto. Nao foi comprovado bypass do delete_view |
| R-02 / P0 | ModelForms comuns nao mostram trava de versao equivalente a importacao de magias | Duas sessoes editando o mesmo catalogo/usuario; conflito deve preservar a segunda edicao, nao overwrite silencioso |
| R-03 / P0 | UserAdmin padrao e mudanca de cargos sensivel | Ensaiar retirada do ultimo Administrador, autoelevacao, conta inativa e perda de cargo entre GET e POST; nao mudar conta real para provar |
| R-04 / P1 | subclasses_count chama relacionamento por objeto; muitos campos relacionados | Medir queries/latencia/payload por tela com dados representativos; annotate/select_related/prefetch so onde necessario. Nao atribuir lentidao a N+1 sem medir |
| R-05 / P0 | Limites/formatos diferem entre importadores; XLSX e arquivo compactado | Conferir limites no proxy, request, parser, quantidade de linhas e expansao ZIP; validar MIME/conteudo sem rodar carga destrutiva em producao |
| R-06 / P1 | Capturas e medidas de layout nao cobrem toda a acessibilidade | Teclado, foco, leitores de tela, contraste, erro, zoom real 200% e reducao de movimento nos fluxos novos. Alvo 44 px e meta de produto, nao laudo WCAG automatico |
| R-07 / P0 | Backup percorre consultas sequenciais sem manifestar um snapshot global | Validar consistencia entre tabelas durante gravacoes, restauracao em clone, memoria e duracao; transacao atomic sozinha nao garante snapshot coerente em todo isolamento |
| R-08 / P1 | Testes existentes cobrem estruturas e varias protecoes, nao observacao do operador | Aceite com outro admin/Staff usando tarefas reais em DEV; erro de rota/tipo/selecionado, dados vazios, redes lentas e retorno de sessao expirada |

## 5. O que funciona e deve ser reaproveitado

Nao transformar o plano em reescrita dos motores do produto:

1. Exportador: schema permitido, preview, ticket assinado vinculado ao usuario,
   expiracao, limites e LogEntry. Reutilizar `catalog_export.py`; trocar adaptador/UI.
2. Importador de magias: plano assinado, fingerprint de classe/alvo e lock.
3. Legado de mestres: importacao idempotente, previa assinada, conferencias de saldo
   e identidade. Nao duplicar creditos nem inferir novo vinculo pelo nome apenas.
4. Concessao de conquista usa `conceder_conquista`; reclassificacao de cosmetico
   tem servico com confirmacao e protecoes de oferta/conflito.
5. Resgates de evento, creditos sociais, curtidas e varios recibos ja possuem admins
   de leitura. Preservar essa imutabilidade no destino novo.
6. Biblioteca de tags ja possui validacao, revisoes e motivo; mover a apresentacao
   sem perder contrato, checksum e historico.
7. A busca de itens por `?q=100` retornou 200 nesta conferencia. O erro relatado antes
   nao foi reproduzido agora; manter como caso de regressao, nao como bug atual provado.
8. Autocomplete de inventario, mensagens de estado, alguns focos/targets mobile,
   rolagem local e testes de zoom ja existem. Sao bases parciais, nao aceite da nova UX.
9. A segunda autenticacao do console e o segredo de API exibido uma vez sao
   protecoes reais. Nao remove-las para simplificar a aparencia.

## 6. Cobertura por recurso e arquivos

[Inventario de destino](20261106-admin-inventario.md) enumera cada um dos 75 modelos,
modo de escrita previsto e sua area. Inclui rotas fora do registry: chaves,
exportacao, biblioteca de tags, console, editor, revisoes e participacao de mestre.
E um mapa de planejamento: nao atribui acesso a usuarios nem declara telas prontas.

| Pacote de mudanca | Arquivos existentes a tratar | Achados |
| --- | --- | --- |
| Politica e identidade | `home/permissions.py`, `home/badges.py`, `home/views.py`, `home/master_hub.py`, `home/models.py`, `home/apps.py`, `bonfire/settings.py`, comandos de acesso e recuperacao | 01-06, R-03 |
| Shell e navegacao | `home/templates/admin/base_site.html`, `home/templates/admin/index.html`, `home/admin_navigation.py`, `home/templates/home/components/header.html`, `home/templates/home/base.html`, CSS/JS admin, URLs | 07-16, 18, 21 |
| Edicao de catalogo | `home/admin.py` (mixin, inlines, imports), `home/conquista_admin_form.py`, `home/security.py`, editores/revisoes e templates de importacao | 17, 19-23, 33, R-02/05 |
| Aparencia/recompensas | `home/admin.py` (TbCosmetico/UsuarioCosmetico/Conquista), `home/cosmetics.py`, `home/cosmetic_entitlements.py`, `home/conquistas.py`, `home/event_cosmetics.py` | 24-26, 31-32 |
| Economia/personagens/bot | admins de transacoes, personagem, revisao e Bot*, servicos de ledger, `home/master_legacy.py`, `home/master_legacy_admin.py`, `home/master_commercial_admin.py` | 27-32 |
| Operacao e chaves | `home/admin.py` (backup/console), `home/db_access_admin.py`, `home/db_access_models.py`, `home/catalog_export_admin.py`, templates correspondentes | 34-40, R-07 |
| Moderacao/auditoria | `home/profile_comments_admin.py`, `home/profile_comments.py`, `home/db_access_models.py`, adaptadores de audit e recibos | 41-42 |
| Aceite focado | `home/test_admin_*`, testes de permissoes por dominio, exportacao, chaves, importacao, conquistas e ledger | R-01/02/03/04/05/06/07/08 |

Nao refatorar `home/views.py` inteiro nem reescrever migrations historicas para
limpar estilo. Cada pacote extrai somente seus servicos/guards para a estrutura
`home/gestao/` proposta no plano principal.

## 7. Sequencia de fechamento incorporada ao plano

### Marco A: prova de uso antes de multiplicar telas

- P0/P1 da arquitetura recebem o inventario e estes achados como entrada.
- Desenhar Inicio, Pessoa/Acesso, Catalogo e Conceder com o header compartilhado.
- No prototipo, operador encontra jogador e libera um cosmetico sem PK/JSON/origem
  tecnica; alvo de ate dois minutos sem orientacao externa.
- Reprovar se os botoes apenas encaminharem ao mesmo ModelAdmin.

### Marco B: primeira entrega funcional e segura

- Politica e matriz aprovadas; Staff nao equivale a superusuario.
- Concessao e consulta com fonte, recibo, motivo e preservacao de compra.
- Cargos e acesso efetivo legiveis; is_staff nao aparece como cargo na nova UI.
- Modelo legado ainda pode existir durante o ensaio; nao chamar isso de remocao final.

### Marco C: substituir os dominios em paralelo

- Regras/catalogo: ADM-17/19/20/22/23/33 e revisao/publicacao generica.
- Mundo/comunidade: mesma infraestrutura, filas de revisao e ADM-41.
- Economia/operacao: ADM-27 a 40, comandos em vez de edicao de provas.
- Auditoria e tarefas longas sao contratos comuns, nao implementacoes diferentes
  em cada frente. Um integrador controla schema, policy, shell e URLs.

### Marco D: identidade e retirada definitiva

- Equivalencia de direitos ensaiada, replay/upgrade e rollback.
- `is_superuser` preservado; `is_staff` removido do modelo/banco e dos consumidores.
- Todos os recursos do inventario tem destino aceito; rotas antigas nao continuam
  necessarias para tarefas correntes nem deixam endpoints de escrita esquecidos.
- Publicar pelo `/site-update` monitorado e conferir a entrega. Push nao e deploy.

**Prioridade nao e implementar 42 correcoes isoladas no painel velho.** E usar os
achados como requisitos da substituicao, aproveitando servicos seguros existentes.
Uma contencao de P0 no admin atual pode ser separada caso aprovada, mas nao e a
reestruturacao pedida e nao deve ser vendida como conclusao.

## 8. Controle de aceite e lacunas

Para cada ADM/R registrar: responsavel, destino, prova de antes/depois, teste
proporcional ao risco, aceite do operador e estado publicado. Nao basta teste 200.

Estados permitidos: confirmado, projeto aprovado, implementado em DEV, validado
pelo operador, publicado, retirado antigo; riscos podem ser descartados com prova.

Capturas mais uteis, no diretorio privado indicado na secao 1:

| Arquivo | O que documenta |
| --- | --- |
| `index-1440.png` / `index-390.png` | Navegacao por modelos, duplicacao de introducao e header mobile |
| `groups-1440.png` | Cargos realmente disponiveis na tela conferida |
| `inventory-detail-1440.png` | Concessao apresentada como relacionamento de tabelas |
| `class-detail-390.png` | Comandos empilhados antes do primeiro campo |
| `master-transactions-detail-1440.png` | Valor e saldo expostos como campos editaveis |
| `item-search-1440.png` | Busca numerica que respondeu normalmente nesta rodada |
| `spell-import-1440.png` / `legacy-import-1440.png` | Importacoes com entradas e contratos diferentes |
| `export-1440.png` / `console-locked-1440.png` | Exportador separado e console com desbloqueio adicional |

O inventario e a auditoria desta rodada estao feitos. Continuam pendentes a
aprovacao da matriz de cargos, o prototipo e a implementacao. Nenhuma conta foi
promovida, meta retomada ou dado de negocio alterado por este levantamento.
