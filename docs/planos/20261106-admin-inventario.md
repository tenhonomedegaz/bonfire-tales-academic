# Inventario de destino do admin

Data: 06/11/2026. Planejamento, nao permissao instalada nem telas implementadas.
Fonte: [registry.json](../qa/admin-audit-20261106/registry.json), 75 modelos.
Complementa [auditoria](20261106-auditoria-admin.md) e [arquitetura](20261106-central-gestao.md).

## 1. Convencoes

- **Editor**: formulario de dominio com campos permitidos e validacao; nao CRUD universal.
- **Comando**: escrita por servico, autorizacao/escopo, motivo, idempotencia e auditoria.
- **Leitura**: prova/recibo/historico; corrigir por evento ou reconciliacao, nao editar o passado.
- **Tecnico**: acesso restrito a Administrador, sem navegar por tabela como tarefa comum.
- Areas: Pessoas; Aparencia; Regras; Mundo; Comunidade; Economia; Operacao.
- Todos os estados abaixo: **inventariado; implementacao pendente**.
- Cargo de mestre, Fogueira, colaboracao ou badge nao concede acesso de equipe.
- Preservar registros, PKs, vinculos e fontes. Destino interno nao significa apagar modelo.

## 2. Modelos registrados: uma linha por recurso

| Modelo atual | Area/destino por tarefa | Escrita prevista |
| --- | --- | --- |
| auth.Group | Pessoas / Cargos e acesso efetivo | Comando de cargo; matriz aprovada, nunca grant-all |
| auth.User | Pessoas / Identidade, cargos e seguranca | Comandos separados; migracao de identidade, Administrador = is_superuser |
| home.AsaasCheckoutOrder | Economia / Pedidos e conciliacao | Leitura; comando de conciliacao, sem alterar status manualmente |
| home.BotCharacterLog | Comunidade / Historico integrado da ficha | Leitura do bot |
| home.BotDedicatedRank | Comunidade / Ranks dedicados | Leitura; eventual comando validado na integracao do bot |
| home.BotKeyValueStore | Operacao / Diagnostico de integracao | Tecnico/leitura com campos redigidos e allowlist |
| home.BotMember | Pessoas / Vinculo Discord e beneficios | Leitura; comando de identidade/beneficio, sem flags arbitrarias |
| home.BotQuest | Comunidade / Missoes e autoria | Leitura; comando de revisao de missao, sem CRUD bruto |
| home.BotSchedulerJob | Operacao / Trabalhos de integracao | Leitura; comando permitido pela fila, nao editar JSON/job |
| home.BotTransaction | Economia / Conciliacao bot/provedor | Leitura; reconciliacao com recibo |
| home.CosmeticCheckoutOffer | Aparencia / Oferta de loja | Editor de oferta por Administrador com impacto/preco |
| home.CosmeticCheckoutPurchase | Economia / Prova de compra e direito | Leitura imutavel |
| home.DbAccessAudit | Operacao / Auditoria de API | Leitura restrita e filtros de ator/tarefa/recurso |
| home.EventCosmeticOffer | Aparencia / Evento e janela de resgate | Editor validado, janela/preco/previa |
| home.EventCosmeticRedemption | Aparencia / Resgates e fontes | Leitura imutavel |
| home.ManagedApiKey | Operacao / Chaves e integracoes | Comandos criar/rotacionar/revogar; segredo uma vez |
| home.MestreOuroDireito | Economia / Direito permanente | Leitura; correcao por revisao autorizada |
| home.MestreOuroRevisao | Economia / Revisao de direito | Leitura da decisao/recibo |
| home.SocialCreditEntry | Economia / Extrato de creditos | Leitura imutavel |
| home.SocialCreditPolicy | Economia / Politica versionada | Editor de nova versao + comando ativar/desativar com impacto |
| home.SocialCreditReaderRecognition | Mundo / Evidencia de leitura reconhecida | Leitura restrita; nao ferramenta editorial de alterar credito |
| home.SocialCreditRedemption | Economia / Resgates de creditos | Leitura imutavel |
| home.SocialCreditWallet | Economia / Carteira de creditos | Leitura; ajustes por lancamentos |
| home.TbAcessoopcao | Regras / Acesso a opcoes na progressao | Editor contextual da classe/subclasse/opcao |
| home.TbAntecedente | Regras / Antecedentes | Editor com Markdown e tags/referencias |
| home.TbArmadilha | Regras / Armadilhas e perigos | Editor + previa de ficha |
| home.TbAutorizacaoVitrine | Comunidade / Autorizacao comercial | Comando com motivo; preservar impedimento de autoautorizacao |
| home.TbAventuraMestre | Comunidade / Historico de mesas | Leitura; lancar/revisar por servico e prova de autoria |
| home.TbBestiario | Regras / Criaturas e companheiros | Editor + previa de ficha, dados e tags |
| home.TbClasse | Regras / Classe, base e publicacao | Editor em abas, revisao/publicacao por servico |
| home.TbClassehabilidade | Regras / Habilidade dentro da progressao | Editor contextual, Markdown e tags, nunca regra por nome |
| home.TbCondicao | Regras / Condicoes | Editor e previa de referencia |
| home.TbConquista | Aparencia / Regra e recompensa de conquista | Editor assistido + comandos com escopo explicito |
| home.TbConteudoEstatico | Mundo / Paginas e publicacoes | Editor de Markdown, revisao e previa |
| home.TbCosmetico | Aparencia / Catalogo visual | Editor/previa; reclassificacao por comando |
| home.TbEmprestimoPersonagem | Economia / Emprestimos | Leitura; comandos de aceitar/pagar/encerrar previstos pelo dominio |
| home.TbEntregaEventoConquista | Operacao / Entregas de recompensa | Leitura; retry/retomar revisao com escopo e idempotencia |
| home.TbEssencia | Regras / Essencias | Editor contextual de origem e referencias |
| home.TbEventoConquista | Aparencia / Prova de marco | Leitura imutavel |
| home.TbFeitoLenda | Comunidade / Feitos do personagem | Editor/moderacao conforme capacidade e autoria |
| home.TbImportacaoMestre | Comunidade / Fontes legadas importadas | Leitura; nova importacao por plano assinado |
| home.TbItemMagico | Regras / Itens magicos | Editor, Markdown/tags e previa |
| home.TbItemMundano | Regras / Itens mundanos | Editor, Markdown/tags e previa |
| home.TbLinhagem | Regras / Linhagem dentro da raca | Editor contextual |
| home.TbMagia | Regras / Magias e acesso | Editor; importacao assinada e acesso por dados/tags |
| home.TbMapDesenho | Mundo / Atlas e desenhos | Editor no contexto do mapa, escopo de camada |
| home.TbMapLayer | Mundo / Camadas do atlas | Editor com previa e visibilidade |
| home.TbMapMarker | Mundo / Marcadores e locais | Editor no contexto do mapa/territorio |
| home.TbMestreLegado | Comunidade / Fogueiras e identidades | Comandos de vinculo/conciliacao com prova; nome publico separado |
| home.TbOpcaojogo | Regras / Opcoes e escolhas | Editor assistido, tags/requisitos |
| home.TbOrganizacao | Mundo / Organizacoes | Editor de conteudo, imagem, membros e previa |
| home.TbPerfilComentario | Comunidade / Moderacao do mural | Comando de soft remove com motivo e prova |
| home.TbPerfilComentarioCurtida | Comunidade / Evidencia de interacao | Leitura restrita, sem CRUD de likes |
| home.TbPersonagem | Pessoas / Fichas do jogador | Consulta; comandos separados para propriedade/progressao/ajuste |
| home.TbPersonagemAventura | Comunidade / Lancamentos de aventura | Leitura; lancar/reverter por servico preservando fonte |
| home.TbPersonagemRevisao | Pessoas / Historico e comparacao de build | Leitura; reversao por comando com nova prova |
| home.TbPersonagemTreinamento | Pessoas / Treinamentos | Consulta e comandos previstos, nao editar custo/status bruto |
| home.TbRaca | Regras / Raca e origens | Editor contextual e importacao conferida |
| home.TbRecompensaMestre | Economia / Catalogo de recompensas MM | Editor de oferta; preservar preco vitalicio aprovado e recibos |
| home.TbRecursoclasse | Regras / Recursos da progressao | Editor contextual de classe/subclasse |
| home.TbRegiao | Mundo / Regioes | Editor + previa de capa/mapa |
| home.TbRegistroMestreLegado | Comunidade / Fonte e conciliacao de mesa | Leitura; revisao por comando, sem duplicar moedas |
| home.TbReiDaColina | Comunidade / Estado do evento | Leitura; comandos do evento, sem editar holder/preco soltos |
| home.TbRevisaoMissaoBot | Comunidade / Decisoes sobre missoes | Leitura; novas decisoes por servico/recibo |
| home.TbSolicitacaoTranscricao | Pessoas / Solicitacoes de magia | Consulta e comandos com custos/consentimento do dominio |
| home.TbSubclasse | Regras / Subclasse no contexto da classe | Editor com progressao/revisao e tags |
| home.TbTalento | Regras / Talentos origem/geral/epico | Editor generico com tags; nao programar talento por nome |
| home.TbTerritorio | Mundo / Territorios | Editor + mapa/relacoes/previa |
| home.TbTracoracial | Regras / Tracos dentro da origem | Editor contextual com Markdown/tags |
| home.TbTransacao | Economia / Extrato da ficha | Leitura imutavel; ajuste/estorno por servico |
| home.TbTransacaoMestre | Economia / Extrato MM | Leitura imutavel; ajuste/estorno por servico |
| home.TbUsuarioConquista | Aparencia / Conquistas do jogador | Consulta; conceder/revogar fonte manual por comando |
| home.TbUsuarioCosmetico | Aparencia / Inventario e fontes do jogador | Consulta; concessao/retracao manual por comando |
| home.TbVerificacaoMesa | Comunidade / Historico de verificacoes antigas | Somente consulta; sem nova confirmacao manual de realizacao. Atividade atual vem do historico conciliado do bot/planilha |
| home.UserAccountMergeReceipt | Pessoas / Historico de fusao de contas | Leitura restrita e imutavel |

## 3. Rotas e tarefas fora do registry

| Entrada existente | Destino de gestao | Fonte a preservar |
| --- | --- | --- |
| Inicio e sidebar do admin | Inicio e navegacao por tarefa | `admin_navigation.py`, `templates/admin/index.html` como inventario, nao como nova UI |
| `/admin/catalog-export/` | Operacao / Exportar catalogos | `catalog_export.py`, tickets, limites, LogEntry; capacidade por tabela/coluna |
| `/admin/api-keys/manage/` e endpoints de ciclo de chave | Operacao / Integracoes e chaves | `db_access_admin.py`, scopes e hash, sem publicar segredo |
| `/admin/tag-library/` e download | Regras / Biblioteca de tags | Validacao, motivo, revisoes/checksum e consumidores genericos |
| `/admin/markdown-editor/` | Editor contextual/previa de conteudo | Renderer/sanitizacao compartilhados, nao editor isolado obrigatorio |
| `/admin/server-logs/` | Operacao / Diagnostico e manutencao separados | Desbloqueio; substituir shell como rotina por comandos controlados |
| `/admin/download-backup/` | Operacao / Backups verificados | Corrigir manifesto/completude antes de chamar completo |
| Restaurar backup, mapa e sync no console | Operacao / Importacao e restauracao | Previa/backup/identidade/locks; cada tipo de pacote explicito |
| Importadores de classe/raca/essencia/traco/talento/opcao/magia | Regras / Importar no recurso escolhido | Parsers existentes, contrato assinado e conflitos; nivel de protecao unificado |
| Importar/vincular/conferir legado de mestres | Comunidade / Fogueiras e conciliacao | `master_legacy.py`, fonte original, autoria e idempotencia |
| Painel de mestre e revisao de portfolio | Comunidade / Participacao e moderacao | `master_participation.py`, `master_portfolio.py`, `master_hub.py` |
| Jornal, cronicas e denuncias | Mundo / Publicar, revisar e moderar | Views/servicos editoriais e capacidades existentes |
| Reclassificar cosmetico, conceder e reprocessar conquista | Aparencia / Catalogo e recompensas | Servicos atuais; declarar escopo real e operacao longa |
| Ativar/desativar politica de creditos | Economia / Politica versionada | `SocialCreditPolicyAdmin`/servico, exclusividade e confirmacao |
| Fusao de contas/validacao de email | Pessoas / Identidade e conciliacao | `email_identity*.py`, recibos; nao repetir exclusao de contas pelo CRUD |
| Login/logout/troca de senha/autocomplete/historico do Django | Compatibilidade autenticada ou substituicao explicita | Inventariar endpoints antes de retirar admin; nao manter escrita esquecida |
| Anexos/imagens/editor do site | Editor compartilhado / Midia | Pendencia anterior de upload, WebP e armazenamento externo permanece separada |

Modelos de dominio que nao aparecem no registry, como perfil do usuario, perfil
de mestre e revisoes de catalogo, devem ser acessados pelas jornadas ja existentes
ou por adaptadores de gestao. Nao registra-los no admin apenas para inflar cobertura.

## 4. Rastreabilidade de implementacao

Cada linha acima recebe, durante execucao, uma tarefa com:
`capacidade | servico/consulta | pagina/rota | validacao | efeitos | teste | estado | evidencia`.

O estado atual e inventariado para todas as linhas, nao aprovado ou implementado.
Responsabilidade por dominio no plano principal; unico integrador para identidade,
schema, policy, auditoria e shell. Nenhuma linha autoriza um cargo novo a escrever
automaticamente nem autoriza excluir historicos/tabelas na migracao.
