# Referencia publica de pendencias - 09/11/2026

O codigo deste marco foi commitado na origem indicada abaixo. Menções a falta
de commit/push no levantamento descrevem checkpoints anteriores; implantacao,
publicacao de dados e aceite na producao continuam separados e pendentes.

Origem: codigo operacional b9920a3343f7909cc74815e2a4a8fb0d6718f32e. Relatos anonimizados; estado local nao equivale a aceite na producao. Evidencias e pacotes privados nao acompanham esta copia.

# Pendencias consolidadas - Bonfire Tales

Atualizacao documental: 09/11/2026. Levantamento das pendencias conhecidas nos
relatos, planos e checkpoints consultados; nao e auditoria nova da producao.
O lote local inclui a central de gestao e historias com revisao/devolutiva.
Publicacao do codigo nao equivale a implantacao ou alteracao de dados reais.
Relato nao equivale a causa comprovada. Documentos antigos podem conter etapas
ja entregues: quando nao existe confirmacao atual, o estado e **a revalidar**.

Detalhes dos relatos novos e criterios: `docs/qa/20261108-relatos-consolidados.md`.
Relatos anteriores do builder: `docs/qa/20261106-character-history-levelup.md`.
IDs C01-I04 correspondem ao inventario da copia academica; mantidos para facilitar
orientacao manual. Arquivos citados sao pontos iniciais, nao causas confirmadas.

## Fluxo de desenvolvimento e publicacao

Decisao do PO em 08/11/2026: desenvolver e corrigir primeiro no repositorio
tradicional. Prioridade inicial: bugfix do Cacador (C14-C16, C01/C06), depois
demais relatos de QA. Nesta etapa, somente listar; nenhuma correcao iniciada.

Sincronizar a copia academica posteriormente, em marco separado e com revisao
de dados privados/segredos. Commits no academico devem ser em portugues, com
titulo que identifique a entrega e corpo com mudancas relevantes, limites e
referencia da versao de origem; nao usar mensagens genericas ou numero de versao
inventado. Nao publicar automaticamente o academico a cada mudanca do tradicional.

## P0 - Criador, Cacador e progressao

| ID | Pendencia | Ponto de entrada / criterio de conclusao |
| --- | --- | --- |
| C01 | Concluir unificacao do catalogo/revisao do Cacador, removendo excecoes operacionais sem romper fichas legadas | Em 08/11, revisao limpa publicada pela API generica e conferida: oito Ordens e dado correto. Pins legados preservados. Correcao do criador local aguarda deploy; demais adaptadores/500 nao encerrados. Ver `docs/qa/20261108-hunter-source-investigation.md` |
| C02 | Segredos aparentemente antigos ou ausentes, texto mal formatado | Diagnostico 09/11: preparacao revisada possui 30 Segredos comuns/8 exclusivos, mas pagina de classe nao incorpora a lista; widget ::options leria catalogo vivo antigo (Granada de Luz divergente). Pacote editorial local home/content_packages/hunter_secrets_reference_20261109.json inclui 30 blocos Markdown por Linha/Grau na descricao da habilidade 1020, sem alterar tags/motor/fichas. Teste focado aprovou integridade, revisao imutavel e rota generica. Nao aplicado: API retornou HTTP 530; base do pacote e a ultima publicada documentada, precisa releitura/preview antes de criar/publicar revisao. Catalogo antigo de opcoes/tagging e aceite visual continuam pendentes. Detalhes: docs/qa/20261109-c02-secret-reference.md |
| C17 | Laboratorio reintroduz Cacador antigo quando a classe inicial nao tem revisao | Corrigido localmente: resolve publicacoes de todas as classes, valida contexto unico, cria vinculo/perfil e exige atributo permanente; sete testes focados OK. Aguarda commit/deploy e releitura em producao. Ver `docs/qa/20261108-builder-hunter-legacy-audit.md` |
| C18 | Preparacoes revisadas no laboratorio | Corrigido localmente: adaptador do servico de preparacao fixado na revisao, Linha Mestra/exclusivos automaticos, escolhas opcionais por proficiencia total e bloqueios por nivel de classe. Oito testes C17/C18 passaram e escolha exercitada desktop/mobile. Aguarda commit/deploy. Ver `docs/qa/20261108-builder-c18-preparation.md` |
| C19 | Corrigido localmente na pagina publica de racas: manifestacoes elementais agora recebem o catalogo existente e nao dependem de retrato proprio | Causa: contexto nao enviava opcoes e JS recusava valor sem arte. Teste nas quatro racas/pagina completa/AJAX passou; Playwright desktop/mobile conferiu Ifrit/Sylph e limpeza ao retornar a base. Sem mudanca mecanica, commit ou deploy. Arquivos: home/views.py, raca_detail.html e parcial raca_detail_content.html; evidencias docs/qa/20261108-c19-elemental-desktop.png e mobile.png |
| C03 | Especializacao em Percepcao indisponivel para personagem elegivel | Reproduzido e corrigido localmente para Elfo Lunareth Cacador: picks agora incluem proficiencias por tags; laboratorio revisado oferece especializacao pelo servico da ficha. Oito testes focados passaram; aguarda commit/deploy e QA na producao. Ver `docs/qa/20261108-c03-perception-expertise.md` |
| C04 | Talentos raciais oferecidos sem requisitos; pool racial independente da pool de classe | Correcao mecanica concluida localmente: level-up, criacao inicial, cadeias raciais e magias validas da propria build; candidato nao satisfaz proprio requisito e ASI permanece separado. Tres testes finais e regressoes focadas passaram. Primeira parte em `18dd4b0`; complemento ainda sem commit/deploy. Aceite visual/producao pendente. Ver `docs/qa/20261108-c04-racial-prerequisites.md` |
| C05 | Manobras possivelmente selecionaveis sem elegibilidade | Reproduzido e corrigido localmente: requisitos explicitos N nivel de classe filtrados no resolvedor compartilhado, inclusive snapshot e listas explicitas; Guerreiro 3/Cacador 16 nao libera requisitos de Guerreiro 5/9/13. Dezenove testes focados passaram. Sem commit/deploy; escolhas antigas nao sao removidas automaticamente. Ver `docs/qa/20261108-c05-option-class-level.md` |
| C06 | Corrigido localmente: nova multiclasse gera suas escolhas antes da confirmacao; previa distingue nivel total e por classe | Tres testes focados e navegacao Playwright desktop/mobile; aguarda commit/deploy. Evidencia: docs/qa/20261108-c06-multiclass-flow.md |
| C07 | Corrigido localmente no level-up: Markdown integral pelo leitor compartilhado, seletores principais com busca/realce e opcoes bloqueadas | Teste de apresentacao e tres regressoes C06 passaram; Playwright desktop/mobile, remocao de escolha e sanitizacao conferidos. Subescolhas internas de talentos permanecem nos controles existentes. Sem commit/deploy. Ver `docs/qa/20261108-c07-levelup-presentation.md` |
| C08 | Corrigido localmente: ASI com controles +/- por atributo, dois pontos disponiveis e previa calculada pelo servidor | Mantido contrato existente de +2 ou +1/+1, sem mudar tetos/regras mecanicas. Um teste focado passou (persistencia, atributo invalido e nao duplicacao); Playwright desktop/mobile conferiu pontos, previa, desfazer e remocao do chip. Sem commit/deploy. Evidencias: docs/qa/20261108-c08-attributes-desktop.png e mobile.png |
| C09 | Corrigido localmente: catalogo inclui tracos iniciais reais da linhagem; apresentacao fica em Lore e habilidades em Tracos | Raca base preservada; sem talentos ou tracos futuros. Descricoes raciais integrais pelo Markdown compartilhado. Teste Lunareth passou e Playwright desktop/mobile conferiu tres habilidades, abas e troca sem residuos. Sem commit/deploy. Arquivos: home/views.py, home/static/js/criador.js e criacao_ficha.html; evidencias docs/qa/20261108-c09-lineage-desktop.png e mobile.png |
| C10 | Referencia de Olhos da Verdade Primordial corrigida no fixture: tbRegra/truesight, nao tbMagia/visao-verdadeira | Motor intacto; teste focado confirmou cartoes/URLs distintos e referencia legitima da magia preservada. Ainda aplicar correcao editorial no banco ativo e nas revisoes pertinentes; alterar fixture nao publica dados. Nao reimportar fixture completo nem editar snapshot selado. Fonte: home/fixtures/conteudo.json (traco 2111); teste home/test_racial_sense_reference.py |
| C11 | Confirmacao de nivel falha em outra classe, relato anterior de personagem afetado | Endpoint de confirmacao/logs; nao assumir que todo erro de level-up e do Cacador |
| C12 | Diagnostico local: Instinto de Sobrevivencia existe e exige linhagem humana, nao essencia | Traco 2185 possui requisito editorial Qualquer Linhagem Humana e tag character_prereq:any{lineage:*}. Teste home/test_human_survival_instinct.py passou: disponivel no criador/level-up com linhagem humana; indisponivel com Nephilim sem linhagem; metadados do seletor coerentes. Nao foi demonstrada falha para personagem elegivel nem conferida revisao da ficha relatada. Ampliar acesso para essencias requer decisao de regra/dado; nenhum requisito alterado |
| C20 | Corrigido localmente: filtro reconhece Alento e Descendencia, inclusive alternativas sob negacao | home/racial_prerequisites.py usa escolhas tipadas e set: das fontes efetivas, sem nomes de talentos; nao ter Descendencia Long ou Draco exclui ambos. Nove testes novos/regressoes raciais passaram: opcoes N5, confirmacao/reabertura, restricoes de ramo e valor de escolha nao relacionada. Sem alteracao de ficha real, commit ou deploy; caso da ficha relatada ainda requer QA apos ativacao. Teste: home/test_draconic_racial_prerequisites.py |
| C21 | Magia de Asas Imperfeitas ausente na aba Magias | PO identificou Alento de Vento: Asas Imperfeitas (traco racial 2285): concede Queda Suave 1/descanso longo sem slot. Causa reproduzida pelo contrato real: tag cast sem always_prepared nao entrava na materializacao antiga. Correcao generica local ja cobre o caso, sem regra por nome. Teste novo passou com tags reais, talento racial salvo por nome, personagem N4/Alento de Vento, catalogo vivo e revisao congelada: Queda Suave aparece com origem/usos, sync repetida nao duplica e remocao do talento preserva magia independente. Cobertura anterior: 14 testes focados + teste real Tocado pelo Feerico aprovados. Nenhuma ficha real alterada; falta commit/deploy e aceite na personagem do relato. Fichas existentes recebem a correcao na sincronizacao operacional existente, inclusive ao abrir a ficha privada como dono/staff (GET ja sincronizava antes desta entrega); nenhum novo gatilho ou migracao em massa criado |
| C22 | personagem do relato: pedido relatado de idiomas Infernal, Celestial e Elfico | Anotado para conferir origem comprovada e fluxo de regularizacao pela staff, preservando idiomas existentes; nenhum idioma concedido nesta rodada. Mesmo print de C20 |
| C23 | Mente Velada recusada para Elfo com essencia | Corrigido no dado local: traco 2081 exigia Linhagem Elfica ou Cultura Adotada, apesar de pertencer a pool base do Elfo. Requisito passa a Elfo, Nivel 1+. Sem mudanca no motor/tags. Criacao completa com Nephilim e oferta no level-up passaram; negativos de linhagem especifica/outra raca, Instinto humano e count_as Salarin tambem passaram. Falta publicar dado/revisao consumida; nao reimportar fixture completa. Plano de patch em `home/content_packages/elf_base_talent_requirement_20261109.json` |
| C13 | Sinal Tubatio desaparecido | Confirmar com referencia/PO se foi removido intencionalmente; nao restaurar por suposicao |
| C14 | Falha recorrente ao atingir nivel 5 da classe Cacador como multiclasse, relato com Mutantes | Contexto integral corrigido e matriz valida passa. participante de QA informou em 09/11 que o bug aparentemente foi resolvido; registrar aceite manual do caso e reabrir investigacao se houver nova falha, sem alegar causa raiz comprovada nem aceitar todos os pontos da classe por extensao. Ver `docs/qa/20261108-hunter-post-deploy.md` |
| C15 | Erro HTTP 500 ao abrir ficha apos subir nivel | Confirmacao com rollback/idempotencia coberta. Outro defeito de pin antigo corrigido; incidente historico segue sem traceback. Em 09/11 usuario informou `/jogador/personagens/ID_PRIVADO/`: consulta autenticada atual retorna 404, detalhe administrativo redireciona ao indice e busca personagem afetado nao encontra. Log disponivel apos reinicio so contem os 404, sem traceback original. Nao declarar resolvido nem inferir exclusao. Ver `docs/qa/20261108-hunter-post-deploy.md` |
| C16 | Cacador ausente da lista de classe primaria na captura | Corrigido localmente em 08/11: removida exclusao do criador comum, usando catalogo versionado; aguarda deploy. Evidencias: `docs/qa/20261108-hunter-source-investigation.md` |

Diretriz: tags/dados para mecanicas e Markdown para formatacao. Evoluir o motor
generico apenas quando faltar uma capacidade. Preservar IDs, pins e revisoes
antigas; nao remover `HUNTER_CREATOR_RULESET_CHECKSUM` sem transicao segura.

Conferencia C02 (09/11): catalogo revisado local comparado integralmente ao
World Anvil: 30 comuns (nomes/Linhas/Graus/niveis/textos) e oito exclusivos
(nomes/textos) coincidentes, descontando apenas formatacao. Nao representa
publicacao nem validacao de todas as mecanicas. API segue retornando HTTP 530;
pacote editorial permanece sem aplicacao, aguardando revalidacao da base.

Retirada C02 autorizada pelo PO: controle generico `TbOpcaojogo.arquivado`,
migration 0178, filtros de catalogo/escolhas e PATCH restrito pela API preparados.
Lote de dados com 31 slugs legados em `hunter_legacy_options_archive_20261109.json`.
32 testes focados passaram (arquivamento, API, snapshots, referencia e magias
inatas). Instalar o codigo antes de aplicar esse lote e publicar a referencia;
nenhuma linha real foi excluida/arquivada nesta etapa. Escolhas antigas e seus
efeitos continuam armazenados; novas revisoes nao alteram pins existentes.
Plano tecnico: `docs/architecture/class_catalog_unification.md` e
`docs/architecture/20261104-market-and-catalog-delivery.md`. As etapas antigas
desses planos precisam ser confrontadas com o codigo atual antes da execucao.

## P0 - Importacao, historico e recompensas

| ID | Pendencia | Ponto de entrada / criterio de conclusao |
| --- | --- | --- |
| H01 | Importado exige confirmar nivel 1 para 1 antes de refazer | Corrigido localmente em 09/11: shell N1 sem build, vinculado a fonte do dono e com ledger integral atestado pelo importador, pode configurar diretamente. Banner mostra Configurar ficha importada; GET de subir nivel redireciona ao criador sem gravar level-up. Confirmacao reutiliza rebuild atomico preservando aventuras/economia/ledger. Dois testes focados passaram; teste de fluxo ampliado confirmou bloqueio de nova recriacao apos mesa posterior. Sem alteracao de ficha real, commit ou deploy |
| H02 | Historico mostra 0 PO apesar de regra de calculo | Ledgers/engine/importador; separar valor historico, valor ja pago e saldo devido, sem duplicar credito |
| H03 | Datas conhecidas aparecem como legado | `home/character_log_workbook.py`, delivery e template; preservar data comprovada |
| H04 | Resgates MM aparecem como mestre legado/missao comum | Review/delivery/recibos; origem correta sem novo debito ou pagamento |
| H05 | Mestre e Fogueira ausentes mesmo com missao reconhecida | `home/master_roster.py`, review e template; identidade deve existir sem conta no site |
| H06 | Diferenca entre total declarado e conciliado | `home/character_log_import.py`, matching; explicar por entrada, nao ajustar total arbitrariamente |
| H07 | Busca/vinculo por nome, ID e mestre; submissao de missao ausente incompleta | Review/forms/politicas; evidencia, vinculacao bilateral e recibos idempotentes |

Logs revisados pela staff sao evidencia de participacao. Missao reconhecida pode
conciliar; entrada sem missao ou classificacao fica pendente. Conferir boost,
tempo/arredondamento e aventuras comprovadas. Nao inventar missoes nem subir nivel
automaticamente. Entrega Dragonforce/personagem legado ja foi aplicada por API: nao repetir.

## P1 - Mestres e portfolio

| ID | Pendencia | Ponto de entrada / criterio de conclusao |
| --- | --- | --- |
| M01 | Separar ativos e historicos na vitrine | Filtros/estado de atividade; preservar Fogueira, creditos e portfolio dos antigos |
| M02 | Apresentacao salva dificil de encontrar e acessar | Links claros para editar/ver apresentacao, refletindo estado publicado |
| M03 | Fluxo de revisao/publicacao da galeria pouco claro | Fila acessivel a revisores; autor ve estado; aprovado aparece publicamente |
| M04 | Foto propria e aparencia do mestre | Retrato distinto do avatar da conta e componentes coerentes de portfolio |
| M05 | Importacao trouxe Mesa de Texto indevida e outros extras relatados | Auditar F49, fonte e substituta; invalidar com rastreabilidade, nao apagar historico nem recalcular saldo sem prova |
| M06 | Duplicatas por titulo/data de publicacao, inicio, fim ou resgate | Matching e portfolio; nao unir apenas pelo nome; preservar origem manual/sistemica |
| M07 | Quantidade de aventuras ausente mesmo havendo registro | Priorizar bot/recibo comprovado; distinguir boost base de bonus de rank e valor privado legado |
| M08 | Paginacao e navegacao da vitrine/portfolio pouco intuitivas | Conferir estado atual apos correcoes anteriores; filtros preservados e links visiveis |
| M09 | Vinculacao automatica Discord -> Fogueira -> permissao de mestre | Correcao generica ja entregue; falta aceite integrado em cadastro/login de conta nova e antiga, sem contornar suspensao |

## P1 - Gestao e autorizacao

| ID | Pendencia | Ponto de entrada / criterio de conclusao |
| --- | --- | --- |
| A01 | Concluir substituicao do admin por fluxos de tarefa | Base local adaptada do portal equipe do portal: sidebar, painel, seis filas persistidas e historico, pessoas/cosmeticos/cargos integrados. Registro de treino comprovado ja ligado ao servico real, com previa/confirmacao. Faltam demais dominios operacionais; concluir ticket genericamente nao altera ficha/saldo |
| A02 | Matriz/editor de cargos e permissoes efetivas | Local: atribuicao de seis cargos, editor de dezessete capacidades em `/gestao/cargos/`, incluindo treino, correcao da ficha, quatro permissoes editoriais existentes e autorizacao de mestres, exclusivo de administrador com previa/confirmacao/recibo. Preserva direitos externos e excecoes; nenhuma conta real promovida. change_tbcronica conserva edicao externa; autorizar_mestres conserva autorizacao da vitrine demonstrativa. Galeria/anuncios/autorizacao de mestre nao exigem mais is_staff quando a permissao explicita existe. Falta migrar outros usos legados de is_staff, commit/deploy e aceite operacional. Plano secao 17 |
| A10 | Mestres, apresentacoes e anuncios no portal | Implementado local: `/mestre/central/` adaptado ao shell da gestao com abas internas, consulta de apresentacao/candidatura preservada e links de portfolio por Fogueira. Anuncios incluidos na fila editorial por permissao, com busca, filtro, link direto e 25 por pagina. Cadastros e vitrine demonstrativa tambem paginados; decisoes usam endpoints/versionamento nativos e dialogo de confirmacao. Autorizacao ainda exige Fogueira, inscricoes continuam fechadas e anuncio pago continua demonstrativo. Sem copiar dados/aprovacoes ou promover contas. 27 testes focados passaram; desktop/mobile conferidos. Um teste antigo da vitrine publica espera link com aba=mestre que o diretorio atual ja nao gera; registrar revisao dessa expectativa fora deste lote, sem declarar suite geral aprovada. Falta commit/deploy e aceite operacional. Proximo: historias das fichas e demais operacoes da staff |
| A11 | Historia na ficha com revisao e devolutiva do Loremaster | Implementado local: dono salva rascunho/envia pela ficha; aviso de aguardando aprovacao, fila editorial e contador para equipe com review_portal_historia. Loremaster aprova ou solicita ajustes com comentario obrigatorio; jogador recebe aviso no site, le devolutiva na ficha/caixa de historias e reenvia. Versoes e pareceres preservados em CharacterStorySubmission, sem tickets duplicados. Edicao posterior invalida aprovacao vigente, versao desatualizada nao e aprovada, reenvio/revisao idempotentes; feedback privado so dono/revisores. Endpoint antigo rejeita tentativa de sobrescrever historia. 28 testes focados distintos e fluxo navegador desktop/mobile passaram, ficha HTTP200 com status. Migration0184 cria somente nova tabela/constraint, sem aprovar historias antigas ou alterar PKs. Falta commit/deploy, configurar permissao no cargo Loremaster e aceite na producao. Notificacao implementada dentro do site, nao Discord/email. Aprovacoes antigas do Discord nao foram presumidas/importadas |
| A09 | Integrar revisoes editoriais ao portal | Implementado local: `/gestao/editorial/` consulta cronicas e trabalhos de mestre nas fontes originais, busca por titulo/autor, filtro por tipo e paginacao de 25. As duas filas nativas usam o shell do portal e link direto ao item, sem copiar conteudo ou criar PortalRequest. Aprovacao/devolucao preserva revisao e auditoria nativas; galeria exige permissao explicita, sem is_staff, e proibe autoaprovacao. 29 testes focados passaram e navegador confirmou ambos os fluxos e layout mobile. Login das revisoes de cronicas corrigido para rota existente. Sem novas migrations nem alteracoes reais. Faltam commit/deploy, aceite operacional e integracao das demais fontes editoriais (historias de fichas, apresentacoes e anuncios de mestre), sem confundir fila de atendimento com publicacao |
| A08 | Correcao de identidade e textos da ficha pelo portal | Implementado local: Pessoas > personagem > Corrigir dados abre atendimento do dono e registra o operador real. Treze campos permitidos, antes/depois, motivo/evidencia, previa assinada, confirmacao, controle de versao e recibo idempotente. Exige capacidade especifica + revisao de ficha + responsabilidade; nao depende de is_staff. Preserva mecanicas, saldo, classe, aparencia cosmetica, privacidade e historia editorial. Historico de valores privados somente para dono/equipe autorizada. 46 testes focados do conjunto e fluxo desktop/mobile passaram. Falta commit/deploy e aceite operacional; proxima etapa: integrar revisoes editoriais existentes sem duplicar fontes |
| A03 | Demais dominios da gestao de cosmeticos | PO dispensou a etapa de revogacao nesta sequencia. Preservar a capacidade administrativa de conceder/gerenciar cosmeticos; nenhuma concessao ou permissao deve ser retirada por esta decisao |
| A04 | Regularizacao de treinos antigos | Implementado local: Pessoas > personagem > Regularizar treino abre atendimento em nome do dono, com operador real no historico. Registrar idioma/ferramenta exige capacidade especifica + revisao de ficha + responsavel, motivo, evidencia, previa assinada e confirmacao. Custo zero, sem alterar aventuras/nivel/carteira; preserva proficiencias existentes, bloqueia conflito com treino pago ativo. Pode concluir o pedido no mesmo comando. 39 testes focados e navegador desktop/mobile passaram; falta commit/deploy e aceite operacional. Novos treinos continuam pagos no mercado |
| A05 | Formulario completo de novos mestres e sua revisao | Conferir implementacao contra perguntas aprovadas; manter solicitacoes fechadas ate liberacao explicita |
| A06 | Atalho da ficha publica para a completa | Corrigido localmente: link "Abrir ficha completa" para dono/equipe pela politica central existente, na mesma guia; oculto na previa como visitante. Tres testes focados passaram. Aguarda commit/deploy e conferencia visual. Sem alteracao de publicidade ou novos acessos. Detalhes em `docs/qa/20261108-public-to-full-sheet-navigation.md` |
| A07 | Adaptar o novo portal da equipe como base da central de gestao | Primeiro marco funcional local: fonte Meagea/portal_bonfire@6a584d1, layout e fluxos adaptados para Django/PostgreSQL sem Flask, SQLite ou login paralelo. Seis filas com responsavel, comentarios, devolutiva/reenvio, conclusao/reabertura, versao e auditoria; 28 testes focados. Falta homologacao visual/operacional e conectar os demais servicos do inventario. Plano secao 17 |

Inventarios detalhados: `docs/planos/20261106-central-gestao.md`,
`docs/planos/20261106-auditoria-admin.md`, `docs/planos/20261106-admin-inventario.md`.
Incluir navegacao na mesma guia, header consistente, busca, formularios/tabelas
legiveis, notificacoes e acoes com permissao explicita.

## P1/P2 - Comunidade, conteudo e integracoes

| ID | Pendencia | Ponto de entrada / criterio de conclusao |
| --- | --- | --- |
| U01 | Toolbar do mural nao responde | `home/static/js/profile-wall.js` e parcial do mural; verificar pagina integrada |
| U02 | Insercao de imagem cortada/ruim no celular | Editor compartilhado/CSS; abrir, inserir e fechar sem perder texto |
| U03 | Upload/clipboard, WebP e armazenamento externo | Projetar limites, consentimento, URLs, limpeza e seguranca; Drive nao presumido como CDN |
| U04 | Paginacao de jogadores mantem scroll no fim | Reposicionar resultados e preservar filtros |
| U05 | Divergencias residuais de cosmeticos e lentidao do perfil | Loja/perfil/ficha/preview; montagem sob demanda e mesmos direitos/assets |
| U06 | Header com largura desalinhada, relato intermitente em 1920x1080 | Reproduzir com zoom/menu/viewports; houve normalizacao relatada, causa nao comprovada |
| D01 | Consistencia de classes/subclasses e pagina x builder | Matriz final; ASI, textos, linhagens e progressao; corrigir dados antes de criar excecoes |
| D02 | Condicoes possivelmente incompletas | Aguardar lista/referencia; nao inventar faltantes |
| D03 | Lacunas declarativas dos talentos epicos/Inspiracao no VTT | Catalogo/tags; concessao ja entregue, sem rastreio desnecessario da mesa |
| D04 | Bestiario: ND separado de XP/PB, icones de tipo e qualidade de blocos | Revalidar relatos antigos contra estado atual; preservar estrutura/tags e IDs |
| D05 | Organizacoes: texto, imagem e colunas desproporcionais; referencias/traducoes como Feather Fall | A revalidar; corrigir Markdown/dados e layout compartilhado conforme causa |
| I01 | Integracao bot-site de missoes, participantes, boosts e recompensas | Uma fonte e recibos; boost dobra base, nao rank; selecionar personagem no resgate |
| I02 | Checkout/periodos/conciliacao apos correcoes anteriores | Validacao integrada segura, sem cobranca real; nao assumir codigo ainda ausente |
| I03 | GET/SET documentado para colaborador e extracao Foundry | `home/db_access_api.py`, `docs/catalog_api.md`, `docs/catalog_export.md`; API e Excel ja existem; formato Foundry depende de definicao |
| I04 | Consentimento de anuncios e requisitos externos | `docs/adsense-consent.md`; confirmar pela conta do titular |
| I05 | Duplicidade de email e consistencia de identidade apos migracoes | A revalidar; codigo anterior existe; nao excluir contas e relacoes sem auditoria/backup |

## P2 - VTT e encerramento

| ID | Pendencia | Criterio de conclusao |
| --- | --- | --- |
| V01 | Inventario e continuidade do laboratorio 2D | `home/vtt_lab*.py`, `docs/vtt_lab.md`; Python-first, reuso de ficha/catalogo/tags |
| V02 | Movimento, dash, magias e semanticas ainda nao cobertas | Conferir capacidades existentes antes de ampliar; testes mecanicos dirigidos |
| V03 | Publicacao privada e evolucao 3D futura | Acesso administrativo por link direto; 3D nao bloqueia entrega 2D |
| Q01 | Aceite integrado final | Ficha nova e legada, classes/subclasses, multiclasse, prerequisitos, recursos, magias, persistencia e mobile; testes pontuais durante correcoes |

## Limites e proximas decisoes

- Este indice cobre pendencias conhecidas do site/VTT, nao retoma Cisco, carreira
  ou operacao do Jarvis, que sao projetos separados.
- Prioridade sugerida: C14-C16/C01 e confirmacao real; H01-H05; conciliacao de
  portfolio; gestao; demais melhorias. Reproduzir antes de expandir a correcao.
- Referencias antigas de arquitetura/progresso nao equivalem a funcionalidades
  ausentes hoje. Backlog geral original alem dos relatos exige auditoria de aceite
  propria; nao ha percentual confiavel apenas pela contagem de itens.
- Para fechar um ID: registrar causa demonstrada, dados versus motor, arquivos,
  teste focado, deploy necessario e aceite. Nao marcar concluido so por commit.
- Nenhuma atualizacao deste documento autoriza escrita em producao ou pagamentos.
