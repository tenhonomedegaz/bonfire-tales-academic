# Evolução Bonfire — rastreabilidade de implementação

Auditoria inicial e retomada: 13-09-2026. Fonte de requisitos: `ARQUITETURA_EVOLUCAO_BONFIRE.md`.

## Leitura obrigatória deste progresso

- Escopo inicial: auditoria estática do plano e do repositório. A seção de retomada ao final registra separadamente implementação e verificações executadas depois dessa auditoria.
- Regra de evidência: arquivo, rota, modelo ou teste existente é **base parcial**, nunca aceite funcional. Testes listados como futuros continuam pendentes, salvo resultado expresso na seção de retomada.
- Estados: `0 não auditado`; `1 auditado com lacunas/contratos`; `2 implementação parcial testada`; `3 aceite regional integral`; `4 fechamento integrado comprovado`. A base inicial foi 16/80, sem testes executados.
- Não contar D01–D08: são critérios de qualidade do documento de arquitetura, não implementação do produto.
- Q14 pertence ao coordenador (`home/static/js/pathbuilder.js` e testes). A correção do cliente passou em testes controlados de navegador; o aceite integral continua em andamento.

## Inventário de evidências estáticas

| Área | Base encontrada | Lacuna perante a arquitetura |
|---|---|---|
| Construção | `home/character_engine.py`, `picks.py`, `pathbuilder.py`, `character_history.py`; `TbPersonagemRevisao` em `home/models.py` | Snapshot de build não fixa revisão imutável de conteúdo/ruleset nem oferece regularização de rework. |
| Ficha/magia | `spellcasting.py`, `magic_workshop.py`, `resource_engine.py`, endpoints e JS de ficha | Contrato único e provas de persistência/contexto ainda precisam ser aceitos por cenário. |
| Social | `TbCronica`, criação/edição/revisão em `home/views.py`; `social.py` para perfil | Não há, na leitura, revisão publicada separada, reação de crônica, comentário, denúncia ou notificação. |
| Economia | `TbTransacao`, `TbPersonagemAventura`, `market_services.py`, checkout Asaas | Não há ledger de moeda social, oferta/direito genéricos, eventos persistidos/entregas idempotentes ou resgate comunitário. |
| Cosméticos | `TbCosmetico`, `TbUsuarioCosmetico`, `cosmetics.py` | Catálogo existe; fontes de aquisição, empréstimos/direitos e manifesto artístico pedidos não estão fechados. |
| Bot/Colab | `discord_user_id`, tabelas `Bot*` sem gestão Django, `permissions.py` e `badges.py` | Permissão ainda consulta identidade/e-mail do bot; falta contrato de autoridade, reconciliação e entrega recuperável. |
| Bestiário | `TbBestiario`, importadores/refinadores, tags e `test_bestiary_refinement.py` | Campos e pipeline existem, mas não há prova estática de auditoria integral, classificação canônica, retagging e reconstrução do acervo. |
| VTT/Foundry | `export_personagem_vtt.py` (contrato Bonfire v1.1) e `home/vtt.py` local não versionado | Não há pacote Foundry auditável neste repositório, manifest, compêndios ou adaptador Actor/Item. |

## Checklist rastreável Q01–Q24

`Base` é referência estática a reaproveitar; `próximo aceite` é obrigatório antes de marcar concluído.

| ID | Estado | Base estática | Próximo aceite/gap |
|---|---|---|---|
| Q01 busca de magias | 2 | `spell_picker.js/css`, templates de criação/level-up/ficha/oficina, `criador.js`, `test_spell_picker.py`, `spell_picker.e2e.cjs` | Componente compartilhado PT/EN sem acentos, círculo, contagem, vazio, resumo focável e preservação de escolhas/limites. E2E Chromium/Django/PostgreSQL 1/1 aprovado, cobrindo os quatro fluxos, catálogo reconstruído e select nativo; visual1280/360 inspecionado. `scratch/evolucao-q01/e2e-acceptance.txt`. Sem JS, permanecem as listas originais; desligamento por retirada do carregamento do componente e recarga, sem migração de dados. Falta fechamento integrado do objetivo; o ensaio não conclui criação/avanço de uma ficha inteira. |
| Q02 slots preservam aba | 2 | `resource_commands.py`, `spell_slots.js`, `http.js`, migração 0103, testes de comandos/migração/browser/E2E | Fluxo real com recibo durável, versão, conflito, timeout e alternativa HTML validado em PostgreSQL isolado; consulta canônica corrigida nesta recuperação. Gates de implantação no banco alvo e fechamento integrado continuam pendentes. Evidências na retomada Q02 abaixo. |
| Q03 Mago da Guerra/Abjuração | 2 | `magic_workshop.py`, `test_transcription_focus.py`, `test_q03_identity.py`, E2E de transcrição e partial comum | Custo base/foco/total explícitos nas duas fontes; registro da autorização acompanha foco atual. Testes regionais e visual abaixo. A causa do relato na ficha legada real ainda requer inventário de FK/versão; não há evidência para corrigir dados em lote. |
| Q04 clérigo 18+ | 2 | `cleric_slot_repair.py`, comando `repair_cleric_slots`, fixture e `test_cleric_slot_repair.py` | Fixture corrigida: slugs canônicos e 5º círculo com 3 slots em 18–20. Reparo atômico/repetível recusa divergências, preserva IDs/gastos. 4/4 testes (tabela 1–20, ficha e consumo18–20) e E2E1/1 com visual1280/360: `scratch/evolucao-q04/{regional,e2e}.txt`. Implantação real e revisão editorial de outras anomalias continuam pendentes; operação em `OPERACAO_SLOTS_MAGIA.md`. |
| Q05 Caçador/Estilo | 1 | `prepare_ranger_rework`: referência associa Estilo a Preparos de Caçada no nível 2; extração e comparação testadas | Ativação depende de revisão imutável, resolvedor e implementação 4A.1/4A.2. |
| Q06 Humano/Multitalentoso | 2 | `views.py`, `test_talento_humano.py` | Leitor distingue exceção negativa de exclusividade de linhagem; Multitalentoso disponível nas quatro linhagens aos13, incompatível com Cultura Adotada em Erthari nas duas ordens. 14 testes regionais aprovados: escolha real, talento geral sem ASI nem consumo da origem, duplicatas, prévia/POST, permissões/CSRF e consumidores de identidade/laboratório. `scratch/evolucao-q06/{before,regional}.txt`: quatro falhas reproduzidas antes da correção. Sem alteração de dados reais; aceite visual e integrado final pendentes. |
| Q07 Druida/Ordem Primal | 2 | `primal_order_repair.py`, comando/fixture, motor/ficha e testes Q07 | Escolha única no nível2 de Druida; Guardião com proficiências e Xamã com dois truques extras vinculados ao Druida e bônus de Sabedoria mínimo1. Reparo atômico/repetível preserva IDs/escolhas e recusa divergências. Sete testes aprovados em `scratch/evolucao-q07/compatibility-retry.txt`; três consumidores e um E2E aprovados em `acceptance.txt`, visual1280/360 inspecionado. Menu aninhado de Marca Planar preservado. Operação em `OPERACAO_ORDEM_PRIMAL.md`; implantação, versionamento e aceite integrado pendentes. |
| Q08 Iniciado em Artífice | 2 | `picks.py`, adaptadores da ficha/laboratório, templates/JS e testes Q08 | Restrição de artesão interpretada; proficiências manuais/de classe/de tags marcadas “já proficiente” e bloqueadas também no servidor. IDs/slugs equivalentes não duplicam a escolha; opção editável do laboratório pode ser retirada. O texto atual não concede substituição por outra categoria. Sete testes regionais em `scratch/evolucao-q08/regional-ready.txt`; laboratório/E2E2/2 em `acceptance.txt`; E2E visual final1/1 em `visual-final.txt` e teste de navegador Q08 do laboratório1/1 aprovados. Visual1280/360 inspecionado, seletor móvel corrigido. Implantação e aceite integrado pendentes. |
| Q09 talentos do laboratório | 2 | `pathbuilder.js`, `pathbuilder.html`, `pathbuilder.browser.cjs` | Recusa por orçamento explicada junto aos talentos; escolha elegível preservada; revisão exige resposta atual e ausência de pendências obrigatórias. Testes regionais aprovados; aceite integrado pendente. |
| Q10 avanço após magias | 2 | `pathbuilder.py`, `pathbuilder_spells.py`, `test_pathbuilder_spells.py`, `pathbuilder_review.e2e.cjs` | Revisão após Magias; origem por classe, truques/conhecidas, aquisição mínima do grimório e teto de preparo validados pelo contrato. Mesma magia em classes distintas; preparo da base reversível; legado com origem ambígua pede seleção; concessões inatas preservadas. Validação regional registrada no checkpoint; aceite integrado do laboratório pendente. |
| Q11 Aliança Selvagem | 1 | Referência extraída com origem e marcos 3/6/10/14/18, preservando seções subordinadas | Mecânicas, opções menores/maiores, seleção/troca e interface ainda pendentes. |
| Q12 talento nível 4/+1 | 2 | `test_pathbuilder.py`, `js_tests/pathbuilder.browser.cjs`: +1, remoção, orçamento e atributo inválido; seletor elegível no navegador | Aceite integrado dos fluxos e versionamento pendentes. |
| Q13 talentos raciais 5–17 | 2 | `test_racial_milestones.py`: origem específica não vaza pela raça, marcos definidos pelo conteúdo, criação/laboratório/level-up, persistência única | Aceite visual e integrado com o acervo completo pendente. |
| Q14 Resiliente/rajadas | 2 | `pathbuilder.js`, `pathbuilder.css`, `pathbuilder.browser.cjs`, `test_pathbuilder.py`, `test_pathbuilder_e2e.py` | Dez cenários controlados e E2E Chromium/Django/PostgreSQL aprovados no fixture: uma salvaguarda, retirada/recolocação, reload, rajada de atributos e recuperação do orçamento. Suíte antiga de 291 interrompida (exit -1), sem aprovação total; base real em uso não foi alterada. |
| Q15 Sangue Planar nível 1 | 2 | `test_planar_creation.py`: Polo/Energia/Elemento, validação, persistência e resistências; `planar_creation.e2e.cjs`: menus reais e limites | Aceite visual integral e efeitos das demais escolhas dependentes da essência pendentes. |
| Q16 select staff | 1 | CSS/admin e testes de responsividade | Verificar aberto/foco/seleção/desabilitado nos navegadores/temas de suporte. |
| Q17 glossário/condições | 2 | `glossario.html`, `glossario.browser.cjs`, `test_glossario.py` | Índice comum implementado, contagem soma os dois catálogos, busca PT/EN/acentos e vazio; dois testes da rota pública PostgreSQL e dois de navegador aprovados; visual 1280/360 inspecionado. Falta fechamento integrado com as demais páginas/estados do sistema visual. |
| Q18 Origem das Sombras | 0 | catálogo de habilidades/magias atual | Auditoria de identidade e magias 3/5/7/9; sempre preparadas sem duplicação. |
| Q19 Guerreiro Atirador | 0 | catálogo classe/subclasse atual | Separar origem e efeito único, preservando referências históricas. |
| Q20 Origem da Tempestade | 0 | catálogo atual | Definir identidade canônica e corrigir vínculo sem duplicar/apagar referência em uso. |
| Q21 Avental/Babador | 1 | `TbItemMagico`, mercados e importação | Estender auditoria para itens/habilidades; decidir alias versus variante preservando inventário/compras. |
| Q22 equipamentos e Força | 1 | `home/static/js/mochila.js`, `test_equipabilidade_itens.py` | Mesma revisão atualiza atributos, perícias, ataques e derivados em equipar/sintonizar/desequipar. |
| Q23 favoritos | 2 | `MarketItemFavorite`, `test_market_favorites.py`, `test_market_favorites_browser.py`: conta–item, POST idempotente, filtro nos dois mercados, recarga e rename de catálogo no PostgreSQL de teste | Aceite regional concluído; ativação/deploy e verificação geral integrados pendentes. |
| Q24 bestiário integral | 1 | `TbBestiario`, importadores, refinadores, tag engine e `test_bestiary_refinement.py` | Diagnóstico e lote integral: classificação, tags, habilidades, filtros, statblocks, referências e consumidores para cada criatura. |

Contagem Q reproduzível: 24 requisitos; `Q=0:3; Q=1:6; Q=2:15; Q=3–4:0`. A contagem segue os estados das 24 linhas Q da matriz acima; estado 2 indica implementação testada, não fechamento integrado do objetivo.

## Entregas 4A — Caçador (obrigatórias e separadas)

| Entrega | Estado | Checklist de fechamento |
|---|---|---|
| 4A.1 versionamento/preservação | 0 | Identidade estável; revisões publicadas imutáveis; ruleset/semântica; vínculo por personagem; resolvedor; inventário/base histórica; imports/admin/fixtures/deploy_sync sem sobrescrever revisão em uso. |
| 4A.2 rework integral | 0 | Matriz da referência; níveis 1–20; dado d6/d8/d10/d12 nos marcos; INT/SAB; conjuração/preparação; Marca; Segredos (3 Linhas, graus 2/5/9/13, pontos e descanso); 8 Ordens desde 3; companheiros/multiclasse; remoção efetiva de habilidades antigas na versão vigente. |
| 4A.3 publicação/regularização | 0 | Novo padrão para novos personagens; legado legível; comparação e escolhas afetadas; aplicação transacional; não duplicar escolhas/inventário/aventuras/recompensas; reversão compatível ou conflito para staff. |

Não é admissível encerrar 4A com apenas infraestrutura, texto, INT/SAB, Marca ou um subconjunto de Ordens/Segredos.

## Checklist das demais frentes do plano

| Frente | Estado | Fechamento rastreável |
|---|---|---|
| Eventos e entrega recuperável | 0 | Evento e entrega persistidos na transação; deduplicação, reserva com token/expiração, retries, revisão e métricas operacionais. |
| Contrato único de ficha | 1 | Criação/laboratório/level-up/ficha/exportação usam cálculo autoritativo e validam servidor. |
| UI e componentes | 1 | Tokens/componentes compartilhados; páginas por área; atualização parcial com fallback HTML; responsividade, teclado, erro e anúncio simulado. |
| Perfil público/privacidade | 1 | Projeção pura e permitida, preview visitante, sem notas/carteira/admin; não sincroniza ficha na leitura. |
| Histórias/comunidade | 1 | Revisões rascunho/submetida/pública; curtir idempotente; comentário/resposta, denúncia, moderação, feed e notificações. |
| Créditos/resgate | 0 | Ledger de conta, autoria/leitura verificada, estorno, resgate de aventura/recompensa com origem distinta e elegibilidade. |
| Conquistas | 1 | Schema de critérios validado, eventos/métricas, concessão idempotente, carga histórica e catálogo inicial verificável. |
| Cosméticos/ofertas | 1 | Separar catálogo/oferta/posse/direito; fontes de aquisição; preview/manifesto para artistas; desempenho/acessibilidade. |
| Asaas | 1 | Pedido/oferta dinâmicos, webhook repetido/timeout/estorno, entrega atômica local e conciliação. |
| Colab/bot | 1 | Autoridade por tabela/campo, conta + Discord forte, adaptador/reconciliação e degradação segura em indisponibilidade. |
| Mestre Ouro | 1 | Regra vitalícia, migração/reconciliação de compradores, texto/layout e decisão de preço/históricos. |
| Bestiário 4B | 1 | Ver checklist integral abaixo. |
| Foundry | 1 | Inventariar pacote externo; prova técnica; manifest/download/changelog; compêndios; importador unidirecional e direitos. |
| Admin/operação | 1 | Navegação por tarefas, preview/checkpoint de lote, pendências/reprocessamento auditado e logs sem segredo. |
| Migração/integridade | 1 | PostgreSQL isolado, cópia de ensaio, classificação content/memória, autoridade de escrita e reversão segura. |

## Bestiário integral (Q24/4B)

- [ ] Reproduzir filtros, classificação, renderização e consumidores de invocação/companheiro/exportação; gerar relatório por criatura e causa.
- [ ] Inventariar `TbBestiario`, `statblock_json` e origem; mapa explícito antigo → classificação canônica.
- [ ] Normalizar tipo/subtipo, tamanho, ND fracionário, XP/PB, procedência, papéis (monstro/NPC/invocação/companheiro), dependências e estado de qualidade.
- [ ] Segmentar e reconstruir traços, ataques, ações, bônus, reações, lendárias/covil, magia, recarga/usos; preservar IDs, aliases, artes e referências.
- [ ] Retaggear com sintaxe, referências e semântica validadas; separar suportado/manual/pendente sem mascarar falha como manual.
- [ ] Aplicar por lote com preview, revisão esperada, checkpoint, retomada idempotente, relatório e reversão preservando referências.
- [ ] Validar **todo** o acervo: cada criatura validada ou pendente identificada com motivo/destino; filtros, ficha, statblock e consumidores consistentes.
- [ ] Enriquecer imagens de equivalentes importados e padronizar catálogos/mundo sem usar isso como substituto do reparo funcional.

## Decisões de PO que bloqueiam ativação (não inventar valores)

| Tema | Decisão pendente |
|---|---|
| Créditos de contribuição | Nome, valores, marcos, janela, tetos e carga histórica. |
| Resgate | Custo, limite, recompensa, elegibilidade e efeito na progressão. |
| Conquistas | Ascendido versus Diamante/Lenda; interpretação de nível 20 sem multiclasse; métrica/limiares de riqueza. |
| Mestre Ouro | Preço inicial, históricos ambíguos e discussão separada de cobranças antigas. |
| Colab | Exclusividades, validade e política durante indisponibilidade externa. |
| Reworks | Prazo de adesão e exceções/reset autorizáveis. |
| Foundry | Sistema-base, versões compatíveis e confirmação do pacote externo mantido. |
| Artes | Dimensões, formatos animados, peso e catálogo editorial. |

## Base estável de maturidade — 20 frentes / 80 pontos

| # | Frente | Nota | Justificativa estática |
|---:|---|---:|---|
| 1 | Arquitetura/eventos recuperáveis | 0 | Apenas proposta; não há modelos/serviço de evento-entrega localizados. |
| 2 | Integridade/migração PostgreSQL | 2 | Fallback SQLite removido e oito testes de configuração aprovados. Cluster de testes isolado criado e identificado antes das migrações; recuperação de dados reais e gates integrais continuam pendentes. |
| 3 | Rulesets/versionamento | 2 | Revisoes, manifestos e resolvedor estrito; guards PostgreSQL 0104/0105. Adaptadores explicitos de habilidades, recursos e limites de escolha preservam valores/nomes/marcos/recuperacao da revisao e usos atuais. Consumiveis versionados exigem contexto de formulas resolvido. Testes: `scratch/evolucao-versioned-resources/`. Inventario somente leitura do Cacador concluido; Universos e ACL de opcoes tambem versionados com adaptador explicito de grupos; 24 testes aprovados em `scratch/evolucao-versioned-options/verified.txt`. Efeitos de opcoes selecionadas usam identidade congelada e copia isolada; 65 testes regionais incluindo calculo numerico em `scratch/evolucao-versioned-effects/verified.txt`. Talentos e antecedentes possuem leitura explicita congelada, incluindo resolucao racial legada e metadados ASI; 16 testes em `scratch/evolucao-versioned-origins/verified.txt`. Fontes raciais automaticas com filtro de cla e efeitos de itens magicos possuem adaptadores explicitos; 9+3 testes em `scratch/evolucao-versioned-racial/`. Contexto comum de features e concessoes fixas agora propagam ruleset explicito; 32 testes de fontes e concessoes legadas em `scratch/evolucao-versioned-context/final.txt`. Calculos completos de equipamento, demais leitores, vinculo das fichas e implantacao pendentes. |
| 4 | Caçador 4A.1–4A.3 | 1 | Extração executável e testada: 211 entradas, oito Ordens, 20 níveis; comparação com 53 habilidades da fixture. Não é snapshot do banco real. Resolvedor versionado, mecânicas, publicação e regularização pendentes. |
| 5 | Criação/laboratório e Q14 | 2 | Q09/Q10 adicionam recusa explicada, revisão final e pendências específicas; validação regional não encerra todos os contratos de criação/laboratório. Nota global mantida22/80. |
| 6 | Magias/slots Q01–Q04 | 2 | Q01 com busca compartilhada nos quatro fluxos e E2E regional aprovado; Q02/Q03 testados; Q04 com fixture/reparo repetível, progressão1–20 e consumo18–20 validados. Diagnóstico legadoQ03 e implantação/aceites integrais ainda pendentes. Maturidade mantida21/80, sem promover a frente por subentrega. |
| 7 | Escolhas/regras Q05–Q15 | 2 | Q06–Q10 e Q12/Q13 com implementações parciais testadas, incluindo limites de magia, bônus de talento e identidade dos marcos raciais. A frente permanece2. Q05/Q11/Q15, versionamento e aceites integrados continuam obrigatórios. |
| 8 | Ficha e atualizações parciais | 2 | Cliente HTTP e slots atualizam cartão e círculo com o mesmo snapshot; timeout/reconciliação e alternativa HTML testados. Demais comandos da seção 5.3 e consistência integrada permanecem pendentes. |
| 9 | Sistema visual/responsividade | 2 | Tailwind 3.4.17/typography servido localmente; E2E do laboratório sem rede externa e inspeção 1280/360 aprovados. Busca unificada do glossário testada. Demais componentes/páginas/estados e build CSS continuam pendentes. |
| 10 | Perfil público/privacidade | 1 | Views/templates/teste público existem; projeção estrita e preview ainda precisam aceite. |
| 11 | Histórias/comunidade | 1 | Crônicas e moderação básica existem; interação/versionamento/notificação faltam. |
| 12 | Créditos e resgate | 0 | Não há ledger de conta/social nem produto de resgate localizados. |
| 13 | Conquistas verificáveis | 1 | Modelos e módulo existem; motor por evento/schema/carga histórica não evidenciado. |
| 14 | Cosméticos/ofertas | 1 | Catálogo/posse existem; oferta/direito e origens completas não. |
| 15 | Asaas | 1 | Pedido, webhook e testes existem; generalização e cenários financeiros ainda não aceitos. |
| 16 | Colab/bot | 1 | Discord/permissions/tabelas externas existem; contrato forte e reconciliação faltam. |
| 17 | Mestre Ouro | 1 | Campos e cobrança existentes; conversão vitalícia não demonstrada. |
| 18 | Bestiário integral | 1 | Modelo/pipeline/testes existem; acervo integral não auditado/reparado. |
| 19 | Foundry/VTT | 1 | Exportador Bonfire e VTT local em trabalho; não há artefato Foundry verificável. |
| 20 | Admin/operação editorial | 1 | Admin organizado e ferramentas existem; operação de novos fluxos/painel não. |
|  | **Total** | **25/80** | Soma: `0+2+2+1+2+2+2+2+2+1+1+0+1+1+1+1+1+1+1+1 = 25`. Frente3 passa de0 para2 por persistência e resolução de versões testadas; integração nas fichas e rework ativado permanecem pendentes. |

## Verificação futura, comandos e gates

Os comandos abaixo são plano de validação; **não foram executados nesta auditoria**. Ajustar o ambiente para PostgreSQL isolado antes dos testes que persistem dados; não admitir SQLite/Mongo como fallback.

```powershell
# Domínio/QA já nomeados pelo plano (executar por fatia afetada)
python manage.py test home.test_criador home.test_pathbuilder home.test_talento_humano home.test_levelup home.test_picks_cap4
python manage.py test home.test_magic_workshop home.test_spellcasting_contracts home.test_resource_engine home.test_magia_teto_swap home.test_magias_filter
python manage.py test home.test_ficha_v2_onda_a home.test_ficha_v2_onda_b home.test_ficha_v2_onda_c home.test_ficha_v2_onda_d home.test_ficha_v2_onda_e home.test_ficha_v2_onda_f home.test_character_history home.test_conceder_item
python manage.py test home.test_asaas home.test_mercado_servicos home.test_equipabilidade_itens
python manage.py test home.test_perfil_social home.test_perfil_preview home.test_tema_swatch_blur home.test_public_presentation
python manage.py test home.test_bestiary_refinement home.test_tag_engine home.test_tag_library_admin home.test_admin_changelists home.test_content_sanitizer
python manage.py test home.test_deploy_sync home.test_export_personagem_vtt home.test_vtt_integration
python manage.py test home.test_responsive home.test_templates_lint home.test_mapa
node --test home/js_tests/map_geometry.test.cjs

# Gate final: suite geral (somente após as fatias e banco isolado)
python manage.py test home
```

Gate E2E final, ainda a criar/selecionar pelo time: navegar criação → laboratório → level-up → ficha e preservar aba; testar Q14 sob rajada/erro/reload; transação/checkout com webhook duplicado/timeout/estorno; publicar/moderar/interagir com história; projeção de ficha como visitante/dono/staff; lote do bestiário e consumidores; exportar/importar Foundry duas vezes sem duplicar Actor/Item, em simples/conjurador/multiclasse/Caçador versionado. O gate só fecha com evidência registrada para dono, outro usuário, visitante e staff quando aplicável.

Gates finais obrigatórios:

- [ ] Todos os Q01–Q24 têm reprodução, regra esperada, correção e teste/aceite correspondente; Q14 validado pelo coordenador.
- [ ] 4A.1, 4A.2 e 4A.3 fechadas separadamente; 4B trata cada criatura; Foundry tem prova/artefato fora ou dentro do escopo confirmado.
- [ ] Decisões de PO acima fechadas antes de ativar economia/direitos dependentes.
- [ ] Suite geral passa no PostgreSQL isolado; E2E passa; migração/reexecução/reversão não perde nem duplica patrimônio, direitos ou fatos.
- [ ] Controles de desligamento preservam dados/histórico; observabilidade não expõe segredos.

## Verificações realmente executadas na auditoria inicial (antes da implementação)

- Leitura estática de `ARQUITETURA_EVOLUCAO_BONFIRE.md`, modelos, rotas, views, exportador VTT e listagem de arquivos com `Get-Content`/`rg`.
- Busca estática de contratos de regras, social, economia, bot, bestiário, Asaas, VTT/Foundry e testes com `rg`.
- Inspeção de `git status --short`: mudanças pré-existentes preservadas em `bonfire/settings.py`, `docs/agentes/regras_retagging_tags_json.md`, `home/urls.py`, além de `ARQUITETURA_EVOLUCAO_BONFIRE.md`, `home/vtt.py` e `home/test_vtt_integration.py` não versionados.
- Nenhum teste, migração, comando Django, banco, integração ou suite geral foi executado.

## Retomada da implementação após interrupção de cota — 13-09-2026

Meta Jarvis: `1b678674-c4db-4833-bbf3-d5fe893a51f5`; rodada preservada: `8bddaa78-3338-4876-9fd9-7878143c4514`. Meta nativa consultada e confirmada ativa com o objetivo integral. A rodada anterior é classificada como **progresso**, pois deixou alterações reais e testes no worktree; seus resultados parciais foram revalidados. A inspeção de processos não encontrou teste Python/Node anterior ativo, portanto não houve reinício de um teste ainda em execução.

### Entrega concreta e lógica

- `home/static/js/pathbuilder.js`: conserva a última prévia e seu orçamento após erro; orçamento só é reutilizável para a mesma base/progressão; bloqueia acréscimos sem orçamento confiável, mantendo remoções; invalida respostas na edição, antes do debounce; separa variantes A/B, reset e importação; oculta comparação desatualizada. Distingue concessões da base das escolhas enviadas, para uma escolha removida não virar concessão fixa.
- Retirada de talento limpa no rascunho local todas as suas chaves de escolha pelo contrato `kind|tipo|classe_id|slug(origem)|ocorrência`, inclusive após reload sem prévia válida. Grupos da prévia antiga do talento retirado deixam de ser editáveis. Escolhas de outras origens são preservadas; recolocar o talento pede novamente seu atributo/subescolhas.
- `home/static/css/pages/pathbuilder.css`: cabeçalho da ficha deixa de cobrir o aviso de erro.
- `home/js_tests/pathbuilder.browser.cjs`: usa cliente/template/CSS reais em Chromium, com respostas HTTP controladas; não conecta ao Django nem ao banco. Dez cenários cobrem erro HTTP/inicial, payload incompleto, rede interrompida, rajadas, respostas fora de ordem, redução de nível, A/B, reload/reset, cardinalidade e retirada/recolocação de Resiliente.
- `home/test_pathbuilder.py`: regressões do servidor para Resiliente duplicado, duas salvaguardas, escolha órfã sem a fonte e payload de 60/4 em regras/sandbox. O motor existente foi reaproveitado, sem alteração em `pathbuilder.py`.
- `bonfire/settings.py`: exige PostgreSQL e falha em configuração ausente/inválida, preservando URL, forma legada `DB_ENGINE=django.db.backends.postgresql` e defaults; alias `postgresql` também aceito. Erro de parse não propaga a URL com credenciais. O trabalho VTT preexistente foi preservado.
- `home/test_database_settings.py`: oito testes em subprocessos isolados, sem conexão ao banco, incluindo compatibilidade legada e ausência de segredo no erro.

### Evidência executada nesta retomada

| Verificação | Resultado / limite da evidência |
|---|---|
| Nove testes de navegador preexistentes | 9/9 passaram nesta retomada antes da nova limpeza. |
| Regressão retirar/recolocar Resiliente antes da correção | Falhou: `escolhas[key]` conservava `['CON']` após retirar o talento. |
| Mesma regressão após correção | 1/1 passou, incluindo erro, reload e preservação de outra origem. |
| `node --test home/js_tests/pathbuilder.browser.cjs` | 10/10 passaram; `scratch/evolucao-q14/browser-results.txt`. |
| Inspeção visual | `q14-desktop.png` (1280 px) e `q14-mobile.png` (360 px), em `scratch/evolucao-q14/`, vistos pelo coordenador. Aviso e última prévia legíveis; screenshots usam ficha controlada, não uma ficha completa real. |
| `venv/Scripts/python.exe -m unittest home.test_database_settings` | 8/8 passaram; `scratch/evolucao-q14/settings-results.txt`. |
| `node --check` nos dois arquivos JS | Ambos aprovados. |
| `manage.py check` com PostgreSQL isolado | Sem problemas, 0 silenciados. |
| Preparação de PostgreSQL | Novo cluster em `scratch/evolucao-q14/pgdata`, somente `127.0.0.1:55439`; `current_database=postgres`, `current_user=bonfire_test`, zero tabelas públicas e `data_directory` conferidos **antes** das migrações de teste. |
| Migrações existentes no banco de teste | 102 migrações de `home` aplicadas, até `0102_mercado_treinamentos_emprestimos`. Nenhuma migração nova ou alteração no banco real. |
| Suíte Django regional | Em execução nesta atualização: pathbuilder/criador/talento humano/picks/level-up; resultado final deve ser registrado abaixo, sem inferir aprovação pelo processo ativo. Handle de retomada `69589`; Python PID `18960`, iniciado 13-09-2026 17:30:58 local; log `scratch/evolucao-q14/django-results.txt`. Revalidar processo/handle antes de qualquer repetição. |

Comandos reproduzíveis usados nesta retomada (o caminho Playwright aponta para uma instalação já existente; pode ser substituído por outra instalação de `playwright`/`playwright-core`):

```powershell
$env:BONFIRE_PLAYWRIGHT_MODULE = "$env:LOCALAPPDATA/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright-core"
$env:BONFIRE_ARTIFACT_DIR = 'scratch/evolucao-q14'
node --test home/js_tests/pathbuilder.browser.cjs
venv/Scripts/python.exe -m unittest home.test_database_settings

# Cluster novo e exclusivo de testes; não reutilizar estas opções no banco real.
# initdb foi executado apenas quando pgdata ainda não existia.
& '../pgsql/bin/initdb.exe' -D 'scratch/evolucao-q14/pgdata' -U bonfire_test --auth=trust --encoding=UTF8 --locale=C
& '../pgsql/bin/pg_ctl.exe' -D 'scratch/evolucao-q14/pgdata' -l 'scratch/evolucao-q14/postgres.log' -o '-h 127.0.0.1 -p 55439' -w start
$env:POSTGRES_URL = 'postgresql://bonfire_test@127.0.0.1:55439/postgres'
venv/Scripts/python.exe manage.py test home.test_pathbuilder home.test_criador home.test_talento_humano home.test_picks_cap4 home.test_levelup --keepdb --noinput --verbosity 1
```

### Pendências preservadas e próximo aceite

Q14 permanece em estado 2: testes do navegador com HTTP controlado e testes do endpoint são evidências distintas, não um E2E entre navegador e Django. Ainda é preciso esse aceite integrado e conferir todos os relatos image31–34 na base alvo. A matriz Q01–Q24, Caçador 4A.1–4A.3, bestiário integral, comunidade, economia, integrações e decisões de PO continuam obrigatórios. Não foram feitos pagamento, publicação, migração no banco real ou ensaio de recuperação dos dados reais.

Maturidade estimada: **18/80 (22,5%)**, mesma base de 20 frentes × 4 pontos. Não representa percentual de critérios de aceite concluídos. A verificação geral final não foi executada e a meta permanece ativa.

## Continuação no perfil helioAI1 — 13-09-2026

Meta nativa consultada: ativa, mesmo objetivo integral. Turno anterior classificado
como **progresso** pelas alterações verificadas no worktree. Não havia processo de
teste anterior vivo. O log regional antigo não continha resultado terminal; não
foi convertido em aprovação. O histórico real foi localizado em
`../AmandaBot/data/SESSOES_AMANDA.md`; o caminho informado no bot não existe.

### Implementação e revisão desta continuação

- Q14: aproveitadas as correções do cliente. Executado o E2E real pendente e
  ampliado `home/js_tests/pathbuilder.e2e.cjs` com rajadas de atributos, orçamento
  derivado do servidor, seis atributos presentes e remoção que libera nova edição.
  A prévia não persiste personagem. Imagens 31–34 extraídas do DOCX e vistas,
  incluindo dois saves, ausência de atributos e 60/4.
- Q17: `glossario.html` pesquisa regras e condições no mesmo índice, conta ambos,
  normaliza acentos/maiúsculas, mantém estado vazio e anuncia o total. Worker
  Terra/medium com escopo exclusivo de template/teste de navegador; revisão pediu
  cobertura de regras acentuadas, catálogo vazio e rótulo acessível.
  `home/test_glossario.py` verifica a rota pública, dados persistidos, contagem e
  escape dos rótulos usados como atributos HTML.
- Dependência visual: o primeiro E2E revelou `tailwind is not defined` com o CDN
  indisponível. A guarda eliminou o erro, mas screenshots mostraram o shell sem
  utilitários. `base.html` agora serve o snapshot Tailwind 3.4.17/typography em
  `home/static/vendor/tailwind/`, com licença, origem e SHA-256 documentados.
  Bundle preservado sem edição; classes inseridas dinamicamente continuam
  compiladas no navegador. Build CSS, outras dependências e demais páginas
  permanecem na frente visual integral.
- `home/test_database_settings.py` e `home/test_pathbuilder_e2e.py`: subprocessos
  decodificam UTF-8 explicitamente. Cinco testes de configuração haviam falhado
  apenas porque stdout UTF-8 era interpretado como Windows-1252; corrigido o
  contrato de codificação, a suíte passou sem enfraquecer as asserções.

### Evidências terminais e limites

| Verificação | Resultado |
|---|---|
| Recuperação do cluster de teste existente | `pg_ctl status` confirmou parado; start recuperou WAL. Caminho exclusivo em `scratch/evolucao-q14/pgdata`, 127.0.0.1:55439; `test_postgres`, usuário bonfire_test, 72 tabelas públicas, 102 migrações home, zero constraints não validadas. Isto não é ensaio de recuperação do banco real. |
| E2E inicial Resiliente | Falhou no fechamento por duas ocorrências de `tailwind is not defined`; verificações de escolhas tinham passado. |
| E2E ampliado após guarda | 1/1 passou em 62,043 s; `scratch/evolucao-q14/e2e-results.txt`. Shell offline ainda sem formatação, corrigido em seguida com asset local. |
| E2E com asset local + rota glossário | **3/3 passaram** em 73,783 s; `scratch/evolucao-q14/e2e-local-assets-results.txt`. Banco separado `test_evolucao_browser` no mesmo cluster isolado, ausente antes do teste; 102 migrações existentes aplicadas. Sem interferência no banco da suíte regional. |
| Visual do laboratório real | `e2e-pathbuilder.png` e `e2e-pathbuilder-mobile.png` em `scratch/evolucao-q14/`, vistos em 1280/360; shell, seis atributos e folha reais formatados com toda a rede externa bloqueada. Não prova todos os estados/páginas/temas. |
| Templates/responsividade/configuração | **12/12 passaram**; `scratch/evolucao-q14/static-settings-results.txt`. Templates/responsividade revalidados após troca do asset: **4/4 passaram**, system check sem problemas. |
| JavaScript/whitespace | `node --check` do E2E e bundle Tailwind, `git diff --check`: aprovados. |
| Glossário no navegador | **2/2 passaram**, executados pelo worker Terra/medium e código revisado pelo coordenador: regra acentuada com `acao`, inglês/maiúsculas, regras/condições, vazio/limpar e catálogos vazios. Tailwind/CSS locais reais; captura em `scratch/evolucao-q17/glossario-1280.png` e `glossario-360.png`, ambas vistas pelo coordenador. Worker revisado e encerrado. |
| Suíte regional de construção | 291 testes em execução, handle **13468**; log `scratch/evolucao-q14/django-results.txt`. Pathbuilder completo já passou; aguardar término dos consumidores criador/talento humano/picks/level-up antes de registrar total aprovado. |

### Próxima ação e escopo preservado

Concluir/revisar resultados regionais, testes/visual Q17 e registrar o resultado
terminal abaixo. Próxima correção curta da onda 1: Q02. Inspeção confirmou forms
de slot com POST/navegação em `ficha_detail.html` e
`views.personagem_usar_slot_magia`; falta resposta parcial que confirme o contador
sem perder aba/foco/rolagem, preservando fallback HTML e permissões.

Maturidade atual **19/80 (23,75%)**, mesma base estável; aumento da frente visual
de 1 para 2 por implementação testada, sem promover toda a frente a aceite.
Caçador integral, versionamento, bestiário, comunidade, economia, integrações,
decisões de PO e verificação geral final continuam obrigatórios. Nenhuma migração
no banco real, publicação ou operação financeira foi executada nesta continuação.

## Retomada Q02 após interrupção de cota — 14-09-2026

Meta nativa consultada e mantida ativa; IDs Jarvis preservados: goal
`1b678674-c4db-4833-bbf3-d5fe893a51f5`, rodada `6551a135-c991-4def-88c2-25cb26505232`.
Turno interrompido classificado como **progresso**: havia implementação e testes
com evidências aproveitáveis. Inspeção de worktree, processos, banco e logs antes
das edições; nenhum processo Python de teste anterior permanecia ativo.

### Implementação recuperada e correções

- Preservados `resource_commands.py`, revisão em `resource_engine.py`/`models.py`,
  migração 0103, classificação de recibos em `deploy_sync.py`, template/CSS de ficha,
  cliente `http.js`/`spell_slots.js` e testes regionais/browser/E2E já aplicados.
  O timeout do corpo JSON já estava corrigido: não foi refeito.
- `views._spell_slot_rows` consultava a chave literal `spell-slot:1`, enquanto o
  motor grava `spell_slot:1`. Corrigidos filtro e lookup para usar `canonical_key`.
  As regressões existentes de renomeação e mudança de teto agora passam. A projeção
  conserva gastos sem sincronizar o banco durante a leitura.
- `views.personagem_usar_slot_magia` agora usa o contrato de operação/versão em
  todos os POSTs. Formulários antigos incompletos pedem atualização sem gastar;
  formulários HTML atuais mantêm proteção contra repetição mesmo com fetch desligado.
  `resource_commands.py` orienta atualizar a ficha para operação inválida;
  `test_resource_commands.py` cobre ausência de ambos os campos ou de apenas um.
- Worker Terra/medium revisou cliente e nove testes browser; alterou apenas a
  espera do fallback em `spell_slots.e2e.cjs`. Revisão do coordenador exigiu
  registrar `waitForNavigation` antes do clique e conferir a URL depois, pois
  `waitForURL` sozinho já resolvia na URL inicial. Worker revisado e encerrado.
- Após um timeout de E2E, o coordenador adicionou marcações de etapas e limites
  de 15s para ações/navegações. `test_spell_slots_e2e.py` conserva o limite total
  de 90s e inclui etapas observadas em eventual erro, sem transformar timeout em skip.
- Novo `docs/OPERACAO_SLOTS_MAGIA.md`: contrato, desativação do cliente, preservação
  dos recibos, implantação e limites. Não autoriza publicar nem reverter a migração.

### Evidências verificadas e limites

Logs abaixo em `scratch/evolucao-q02/`; arquivos antigos foram preservados.

| Verificação | Resultado real |
|---|---|
| Estado do PostgreSQL antes desta retomada | `pg_ctl status` confirmou cluster vivo exclusivo `scratch/evolucao-q14/pgdata`, porta 55439; `test_evolucao_q02_r6` com 73 tabelas, 103 migrações home, zero constraints não validadas e zero usuários residuais. Sem clientes de teste concorrentes. Dump anterior `pre-migration.dump` legível pelo `pg_restore --list`. Nenhuma migração estrutural adicional aplicada nesta retomada. |
| Regional anterior | `regional-results.txt`: 53/53 aprovados; `migration-history-results.txt`: 3/3 aprovados (upgrade/reexecução, restore de build, classificação de memória). São evidências anteriores conferidas, não novas execuções. |
| Logs terminais ausentes ou falhos | `final-regional-results.txt` tinha falhas canônicas e E2E sem fechamento; `browser-final-results.txt` parava após três testes. Não considerados aprovação. `e2e-resumed-results.txt` registrava usuário residual duplicado. |
| Browser revalidado pelo worker | **9/9 aprovados**, `browser-recovery-results.txt`; timeout antes/depois de cabeçalhos, rede, duplo clique, conflito, confirmação, HTML inesperado, foco/aba/rolagem e desativação parcial. |
| Regional servidor após correção canônica | **50/50 aprovados**, 161,678s, `server-recovery-verified-results.txt`: comandos, recursos, conjuração, oficina e histórico. Primeira tentativa do runner não executou testes (`KeyError MIRROR` ao substituir TEST); corrigida para alterar apenas TEST.NAME. Log dessa tentativa preservado em `server-recovery-results.txt`. |
| E2E e consumidores de ficha | **7/7 aprovados**, 65,173s, `e2e-recovery-verified-results.txt`: Chromium/Django/PostgreSQL, templates, responsividade, ficha de conjurador e descanso sem repor consumíveis. |
| Contrato HTML reforçado | **20 testes de comandos aprovados; E2E excedeu 90s**, `strict-command-final-results.txt` (21 no total, resultado FAILED). Este conjunto não é uma suíte integral aprovada. |
| E2E instrumentado | Resultado terminal recuperado na rodada 7: **1/1 aprovado**, 95,891s totais, subprocesso Chromium 75,357s; `e2e-traced-results.txt`. Todos os marcos encerrados, incluindo alternativa HTML e fechamento do browser. Não reexecutado sem necessidade. |
| Verificação estática | `makemigrations --check --dry-run`: nenhuma mudança detectada. `node --check` para cliente HTTP, slots e E2E, e `git diff --check`: aprovados. |
| Visual | Capturas de sucesso 1280/360 em `recovery-visual/` inspecionadas; sucesso móvel e conflito desktop em `recovery-visual-final/` também vistos. Contadores e mensagens cabem nos cartões; resumo do círculo acompanha o snapshot. Ícone de patente indisponível com rede externa bloqueada é limitação registrada do shell, não aceite visual global. |

### Progresso e próxima frente

Maturidade **21/80 (26,25%)**, mesma base de 20 frentes × 4 pontos: frente 6
(magias/slots) e frente 8 (atualizações parciais) passam de 1 para 2 por Q02
implementado e testado. Nenhuma dessas frentes foi promovida a aceite integral;
Q02 permanece em 2. Q14/Q17 mantêm evidências e pendências anteriores; o log
interrompido dos 291 testes de construção não comprova aprovação dos consumidores.

Próxima frente da onda 1: reproduzir Q03 com classe/subclasse/foco e transcrições,
aproveitando a base de oficina já testada, e seguir Q01/Q04 e a matriz integral.
Os demais comandos da seção 5.3, criação/escolhas, Caçador 4A completo, bestiário
integral, comunidade, economia e integrações continuam obrigatórios. Decisões
reservadas ao PO na seção 17.2 não foram inventadas. Não houve migração no banco
real, publicação, operação financeira real nem modificação funcional em projeto
irmão. Verificação geral final ainda não executada; meta integral permanece ativa.

## Rodada 7 — recuperação após reinício e transcrição Q03 — 14-09-2026

Meta nativa integral consultada e ativa. Rodada Jarvis
`9452bbb2-bdb8-4d05-a79f-5ce7bf5e69b5`, mesmo goal `1b678674-c4db-4833-bbf3-d5fe893a51f5`.
A interrupção imediata da leitura não produziu progresso; retomada por inspeção
real. As entregas anteriores de Q02 foram preservadas, sem repetir operações.

### Recuperação de Q02

- `e2e-traced-results.txt` contém resultado terminal OK: 1/1 em 95,891s;
  o subprocesso terminou em 75,357s, dentro do limite de 90s. O registro
  “em validação” foi corrigido. O timeout anterior permanece como falha histórica.
- Inspecionadas capturas `scratch/evolucao-q02/recovery-visual-traced/`:
  móvel com sucesso e desktop com conflito, cartão e círculo consistentes.
- O antigo handle 13468 não foi consultado: execução dos 291 testes interrompida
  com exit -1 conforme recuperação confirmada; log Q14 preservado. Não há aprovação
  global daquela suíte. Os resultados regionais posteriores têm seus próprios escopos.
- Cluster de testes 55439 estava parado após reinício. `pg_ctl` recuperou WAL;
  identidade `test_evolucao_q02_r6`, caminho exclusivo `scratch/evolucao-q14/pgdata`,
  73 tabelas, zero constraints não validadas e zero usuários residuais confirmados.
  Nenhuma migração nova; isto não prova recuperação do banco real.

### Alterações concretas Q03 e lógica

- `home/magic_workshop.py`: o cálculo existente retorna também custo/tempo base,
  escola que concede o desconto, percentual e classe de origem do contrato.
  A regra de desconto não foi alterada nem confundida com identidade de subclasse.
- `home/views.py`: as duas fontes (pergaminho e outro grimório) usam esse mesmo
  detalhamento na prévia, solicitação e transação. A autorização atualiza também
  `detalhes_json`, eliminando desconto antigo após mudança de foco. Sem nova tabela.
- `home/templates/home/partials/transcription_terms.html`: apresentação comum de
  base, benefício e total. Consumida por `pages/oficina_magia.html` e
  `pages/ficha_detail.html`, que foram alterados somente nesse trecho nesta rodada.
- `home/test_transcription_focus.py`: cinco regressões de composição, foco textual
  legado, identidade, repetição e prévia/cobrança nas duas fontes, incluindo foco
  que muda entre pedido e autorização. Reproduziram 1 falha e 4 erros antes da correção.
- `home/test_q03_identity.py`: worker Terra/medium investigou o caminho de escrita
  e criou dois testes com escopo exclusivo. Coordenador revisou e executou:
  POST real do painel/registry, FK, derive/banner e escolha legada sem FK.
- `home/test_transcription_focus_e2e.py` e `home/js_tests/transcription_focus.e2e.cjs`:
  Chromium/Django/PostgreSQL reais, duas prévias na oficina e uma na ficha,
  subclasse no banner, 1280/360px, verificação de largura e erros JavaScript.

### Evidências desta rodada

| Verificação | Resultado |
|---|---|
| Reprodução Q03 antes da correção | 5 testes: 1 falha de desconto desatualizado e 4 erros por detalhamento ausente; `scratch/evolucao-q03/before-results.txt`. |
| Regional transcrição/oficina/conjuração/templates/responsividade | **31/31 aprovados**, 96,661s, `scratch/evolucao-q03/regional-results.txt`; processo terminal exit 0. |
| E2E real da apresentação | **1/1 aprovado**, 59,721s, `scratch/evolucao-q03/e2e-results.txt`; processo terminal exit 0. |
| Identidade pelo registry/painel e legado | **2/2 aprovados**, 12,452s, `scratch/evolucao-q03/identity-results.txt`. |
| Visual | Oficina 1280/360 e ficha móvel em `scratch/evolucao-q03/visual/` inspecionadas; custo base, foco e total visíveis, sem extrapolar largura. Patente externa bloqueada é limitação conhecida do shell. Não é aceite visual global. |
| Estática/schema | `node --check home/js_tests/transcription_focus.e2e.cjs`, `git diff --check` aprovados; `makemigrations --check --dry-run`: nenhuma mudança detectada. |

### Limites e próxima etapa

A fixture separa Abjurador, Guerra e opção Abjuração. O caminho de foco persiste
`TbPersonagemEscolha`; a apresentação lê `TbPersonagemClasse.id_subclasse`.
A causa do personagem legado do relato não foi reproduzida: falta conferir sua
FK e versão de conteúdo. Não corrigir personagens em lote com base nessa hipótese.
As duas transcrições foram exercitadas em fixture mínima; isso não substitui
inventário de dados reais nem versionamento de regras.

Maturidade consolidada **21/80 (26,25%)**, mantendo 20 frentes × 4 pontos.
Comparada aos 19/80 do último relatório Jarvis, incorpora os dois pontos já
registrados na rodada interrompida: frentes 6 (magias) e 8 (atualização parcial)
passam de 1 para 2 por Q02. Q03 agora está em estado 2, mas não aumenta a nota
2 da frente 6: Q01/Q04 e o diagnóstico legado Q03 ainda faltam. Nenhuma frente
recebe estado 3/4 sem o aceite pertinente.

Próxima etapa concreta: Q04, conferir progressão de slots do Clérigo em 18–20
contra tabela Bonfire e consumidores, depois Q01 e demais regressões da onda 1.
O inventário legado Q03 continua rastreado. Caçador integral/versionamento,
bestiário integral, comunidade, economia, integrações, decisões PO e verificação
geral final continuam obrigatórios. Nenhuma publicação, migração no banco real,
pagamento real ou alteração funcional de projeto irmão foi realizada.
