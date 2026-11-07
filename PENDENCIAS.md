# Pendencias consolidadas - Bonfire Tales

Referencia: snapshot da dev em 07/11/2026. Documento para manutencao manual,
orientacao academica e priorizacao, nao certificacao de que todos os fluxos foram
testados. **Aberto** significa relato ou frente sem aceite final registrado.
Status antigos em outros arquivos nao prevalecem sobre as ressalvas daqui.

## P0 - Cacador, criador e progressao

O rework do Cacador NAO esta integralmente concluido. Existem resolucao/publicacao
comuns e revisoes fixadas, mas permanecem adaptadores de origem, escolha INT/SAB,
regularizacao, concessoes e mecanicas residuais. O alias
`HUNTER_CREATOR_RULESET_CHECKSUM` continua por compatibilidade. Nao apagar esse
alias, pins ou revisoes antigas sem migracao e ensaio; nao corrigir com `if cacador`.

| ID | Pendencia e mudanca esperada | Arquivos/pontos iniciais | Aceite pontual |
| --- | --- | --- | --- |
| C01 | Unificar os consumidores reais da revisao da classe, incluindo magias e segredos; substituir excecoes residuais por capacidades genericas | `home/class_publication.py`, `home/versioned_classes.py`, `home/hunter_spells.py`, `home/hunter_views.py`, `home/views.py`, `docs/architecture/class_catalog_unification.md` | Pagina, criador, multiclasse, ficha e VTT usam a mesma revisao; legado preservado |
| C02 | Segredos de Cacador aparentemente antigos; conferir dado publicado e revisionamento antes de alterar motor | catalogos/revisoes no banco, `home/hunter_spells.py`, `home/character_engine.py` | Segredos oferecidos correspondem ao texto/revisao correta; sem duplicacoes |
| C03 | Especializacao em Percepcao nao selecionavel | `home/views.py`, `home/character_engine.py`, requisitos/tags da opcao | Personagem elegivel seleciona e recebe Especializacao; inelegivel e recusado |
| C04 | Talentos raciais aparecem sem requisitos; texto antigo diz incorretamente que substituem talentos de classe | filtros/validacao de `home/views.py`, `home/character_engine.py`, descricoes e tags | Pool racial independente, base + linhagem/essencia; validacao tambem no servidor |
| C05 | Manobras possivelmente selecionaveis sem elegibilidade; relato ainda nao reproduzido | catalogo de opcoes/tags, `home/views.py`, `home/static/js/subir_nivel.js` | Nivel de classe, subclasse e escolhas no lote respeitados; servidor rejeita manipulacao |
| C06 | Multiclasse so resolve escolhas no level-up seguinte; previa parece usar nivel total como se fosse nivel da classe | `home/static/js/subir_nivel.js`, `home/views.py`, templates de progressao | Todas as escolhas da classe escolhida resolvidas no mesmo lote, sem nivel ficticio |
| C07 | Markdown cru, descricoes truncadas, dropdowns extensos e selecao sem destaque | `home/static/js/subir_nivel.js`, `home/templates/home/pages/subir_nivel.html`, leitor Markdown compartilhado | Descricoes formatadas, comparacao e selecao claras, desktop/mobile |
| C08 | Distribuicao +2 por dois seletores +1 e pouco intuitiva | mesmo JS/template; validacao de atributos | Pontos disponiveis, destino, limite e previa claros; sem exceder limite autorizado |
| C09 | Aba Tracos mostra lore da linhagem e omite suas habilidades | criador de ficha, tracos raciais no banco, componentes de previa | Base + skills selecionadas; exemplo Lunareth: Sinal Lunar, Bruma Serenante e Sopro Selenico |
| C10 | Olhos da Verdade Primordial aponta para magia e nao sentido Visao Verdadeira | descricao/tag do talento, catalogo de sentidos, resolvedor Markdown | Card abre a referencia ao sentido; sem excecao por nome no motor |
| C11 | Erro de confirmacao de nivel de outra classe ainda sem causa final comprovada | rota de confirmacao em `home/views.py`, logs anonimizados, revisao e payload | Confirmacao atomica real reproduzida/corrigida; previa bem-sucedida nao basta |

## P0 - Importacao e conciliacao historica

A entrega por API ja existe e cria ficha-base, registros e vinculos, sem reconstruir
build completa. Foram relatadas lacunas na primeira utilizacao. Corrigir de modo
generico; nao inserir regras para um personagem especifico.

| ID | Pendencia e mudanca esperada | Arquivos/pontos iniciais | Aceite |
| --- | --- | --- | --- |
| H01 | Ficha-base importada exigiu confirmar nivel 1 para nivel 1 antes de Refazer do zero | `home/character_history_delivery_api.py`, `home/character_history.py`, `home/views.py` | Inicia diretamente a configuracao do nivel 1 |
| H02 | Historico exibe 0 PO; definir/importar calculo historico e saldo devido sem repetir pagamento | `home/character_history_delivery_api.py`, `home/character_engine.py`, ledgers de aventura/transacao | Valor historico, valor ja pago e novo saldo diferenciados; estorno e replay seguros |
| H03 | Data exibida como legado mesmo presente na fonte | `home/character_log_workbook.py`, `home/character_history_delivery_api.py`, `data_missao`, template do historico | Data conhecida exibida; sem inventar horario ou inverter dia/mes silenciosamente |
| H04 | Resgate MM nao aparece como origem correta e usa mestre legado | `home/character_history_delivery_api.py`, `home/character_log_review.py`, template do historico | Resgate nao e mesa jogada; recibo correto sem novo debito/pagamento |
| H05 | Mestre/Fogueira nao aparece mesmo com missao identificada | `home/master_roster.py`, `home/character_log_review.py`, ledger e template | Mostra identidade/Fogueira mesmo sem conta auth.User |
| H06 | Diferenca entre total declarado e conciliado exige analise por entrada | preview de `home/character_log_import.py`, `home/character_log_matching.py` | Explicar divergencia, priorizar registro comprovado e nao arredondar total global |
| H07 | Busca de conciliacao ainda precisa cobrir nome, ID e mestre de forma ergonomica; submissao manual por mestre nao e fluxo completo | `home/character_log_review.py`, views/forms de conciliacao, politicas | Missao encontrada/vinculada ou criada com evidencia e autorizacao, sem duplicar |

## P1 - Gestao e autorizacao

| ID | Pendencia | Arquivos/pontos iniciais | Aceite |
| --- | --- | --- | --- |
| A01 | Concluir substituicao do admin por tarefas, nao somente trocar CSS | `home/gestao/`, `home/gestao_models.py`, `home/admin.py`, `docs/planos/20261106-central-gestao.md` | Operacoes comuns compreensiveis para nao desenvolvedores |
| A02 | Matriz/editor de Staff, Rulesmaster, Loremaster, Jornalista e permissoes efetivas; retirar dependencia de is_staff; manter superuser como administrador | politicas, auth/models, `home/gestao/policy.py`, `home/admin.py` | Menor privilegio, explicacao do acesso e protecao contra elevacao; migracao ensaiada |
| A03 | Concluir demais dominios e revogacao segura de concessoes manuais | `home/gestao/services.py`, inventarios/recibos, guias de gestao | Concessao/revogacao auditadas sem apagar compra ou direito independente |

Detalhamento e inventario: `docs/planos/20261106-auditoria-admin.md` e
`docs/planos/20261106-admin-inventario.md`. Artefatos brutos privados da auditoria
nao fazem parte desta copia.

## P1/P2 - Comunidade, conteudo e integracoes

| ID | Pendencia | Arquivos/pontos iniciais | Aceite |
| --- | --- | --- | --- |
| U01 | Botoes de negrito/italico/imagem/link/emoji/previa no mural nao respondem em producao | `home/static/js/profile-wall.js`, `home/templates/home/partials/_profile_wall.html`, pagina de perfil e carga do Markdown | Ferramentas operam na pagina integrada, nao somente fixture isolada |
| U02 | Campo de imagem do editor ruim/cortado no celular | componentes do editor, CSS responsivo; `docs/qa/20261104-perfis-e-magias.md` | Insercao acessivel sem corte em mobile |
| U03 | Clipboard/upload de imagem, WebP e armazenamento externo ainda precisam de projeto | editor Markdown compartilhado, futuros endpoints/storage; `docs/qa/20261026-relatos.md` | Consentimento de upload, limites, transparencia/animacao, URL persistente e limpeza; Drive nao presumido como CDN |
| U04 | Paginacao de jogadores deve voltar ao inicio dos resultados | pagina/JS de jogadores e ancora de paginacao | Proxima/anterior preservam filtros e reposicionam a tela |
| U05 | Conferir divergencias residuais de cosméticos entre loja, perfil, previa e ficha; desempenho de imagens e montagem de perfil | `docs/planos/20261026-perfil-cosmeticos-lojas.md`, CSS/JS/componentes de aparencia | Mesmo direito/asset nas superficies, carregamento sob demanda e movimento reduzido |
| D01 | Auditoria editorial e mecanica de classes/subclasses e progressao pagina x builder ainda nao e aceite integral | modelos/tags, leitor Markdown, `home/character_engine.py`, QA de conteudo | Matriz dirigida por classe/subclasse/revisao; evitar duplicacao de catalogos e nomes divergentes |
| D02 | Condicoes possivelmente incompletas: aguarda lista/referencia aprovada | catalogo de condicoes | Nao inventar regras nem adicionar por suspeita |
| D03 | Pendencias declarativas de talentos epicos e futura automacao de Inspiracao no VTT | `home/epic_talent_catalog.py`, verbos/tags, testes de efeitos | Parametros alteraveis por tag; Inspiracao da mesa sem rastreio desnecessario |
| I01 | Concluir integracao de missoes/boosts/participantes e recompensas entre bot e site | `home/master_mission_review.py`, `home/mission_reward_context.py`, servicos do bot externo | Uma fonte de verdade, boost base separado de rank, recibos sem duplo pagamento |
| I02 | Validar fluxos reais de checkout/periodos e conciliacao apos correcoes anteriores | `docs/maintenance-20261105.md`, `docs/integracao_asaas_checkout.md`, webhook e checkout | Nao executar cobrancas reais para testar; nao reabrir bugs ja corrigidos sem evidencia |
| I03 | Melhorar documentacao/extracao GET/SET por catalogo e adaptar Foundry quando formato for fornecido | `home/db_access.py`, `home/db_access_api.py`, `docs/catalog_api.md`, `docs/catalog_export.md` | Chave de leitura limitada, descricoes completas, paginacao e versao; sem SQL remoto |
| I04 | Confirmar consentimento de anuncios e requisitos externos pela conta do titular | `docs/adsense-consent.md` | Nao declarar ativacao/regularidade sem evidencia |

## P2 - VTT e validacao final

Laboratorio 2D existente: `home/vtt_lab*.py` e `docs/vtt_lab.md`. Inventariar os
comandos ja implementados antes de ampliar. Integracao de movimento dinamico,
dash, magias e semanticas ainda nao cobertas deve permanecer Python-first,
reaproveitando os mesmos dados/tags da ficha. Modelo/experiencia 3D e escopo futuro.
Sem demonstracao publica irrestrita: laboratorio deve seguir gate privado/admin.

Antes de fechar uma entrega: testar somente o comportamento corrigido e seus
consumidores de risco; depois executar uma matriz integrada final de criacao,
multiclasse, atributos, recursos, magias, talentos e revisoes. Incluir uma ficha
nova e uma legada. Nao confundir suite extensa com evidencia de fluxo utilizavel.

## Como registrar uma correcao

Para cada ID: reproducao sintetica, causa demonstrada, arquivos alterados,
mudanca de dados separada de mudanca de codigo, teste focado e limites restantes.
O repositorio publico nao tem acesso automatico ao ambiente operacional. Nenhuma
proposta desta lista autoriza alterar dados reais, pagamentos ou contas.
