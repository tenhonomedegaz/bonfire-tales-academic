# Unificacao do catalogo de classes: contratos e limites

## Escopo e decisao

- Objetivo: selecao, publicacao, resolucao e tags de Cacador devem seguir o protocolo das demais classes. A migracao integral ainda nao esta concluida.
- Publicar uma revisao nao deve exigir atualizar `HUNTER_CREATOR_RULESET_CHECKSUM`, reiniciar o site ou abrir um criador separado.
- Isso nao significa que todas as mecanicas estejam generalizadas. Separar catalogo/publicacao de execucao e estado da ficha.
- Este documento orienta a migracao; a publicacao de codigo nao autoriza conversao automatica de fichas nem retirada de mecanicas.
- Evidencia: codigo e pacotes locais. Nenhuma consulta a ambiente, banco, producao ou dados de jogadores.

## Entrega incremental em 2026-11-04

Por solicitacao do usuario, o lote foi limitado para economizar a cota semanal.
O inventario abaixo continua sendo o mapa de trabalho, nao uma declaracao de que tudo foi implementado.

- Implementado: contrato generico opcional `contracts: {"spell_grants": "tags-v1"}` no snapshot de qualquer classe. A API `class-revision` aceita esse campo, inclusive com `changes: []` para uma revisao somente de contrato. Nao publica nem altera pins automaticamente.
- Implementado: leitor comum para uma escolha limitada de magias de circulos diferentes, por tag `spell_selection:any{list:[slug_a,slug_b],qtd:2,always_prepared,extra,requires:lvl{18}}`. Referencias invalidas nao abrem o catalogo inteiro.
- Implementado: adaptadores antigos de concessao/Caminho Final deixam de fornecer magias quando o pin declara explicitamente esse contrato. Pins sem contrato conservam o comportamento anterior.
- Nao ativado em producao: esse contrato exige primeiro completar os dados (80 concessoes de lista, Marca, Familiar de Batalha, Mao Arcana e escolha de Caminho Final). Nunca o ativar somente para esconder o fallback.
- Pendente: normalizar Markdown/progressao/subclasses da revisao publicada, instalar o ponteiro comum, unificar a entrada do criador e remover a dependencia de `HUNTER_CREATOR_RULESET_CHECKSUM`. A variavel e as ramificacoes antigas continuam presentes neste lote para nao trocar silenciosamente a revisao ativa pela fonte legada.
- Fora deste lote: migracao das demais familias mecanicas descritas abaixo; preservacao dos adaptadores e das fichas existentes e intencional.

O checkpoint da sessao no SQLite registra a evidencia anterior de ativacao da revisao `95b5...` pela API. O status `proposed_not_applied` citado abaixo e do artefato historico, nao do estado atual da producao. Esta entrega nao modifica dados remotos.

## Contrato comum e compatibilidade

`class_publication.py` ja oferece `published_catalog`, preflight e ponteiro `TbClassPublication` por identidade de classe.
`VersionedClassCatalog` fornece colecoes congeladas, niveis, subclasses e recursos; publicacao comum exige `presentation_source: catalog`.
O alvo publicado atende novas selecoes. Uma ficha existente usa seu vinculo explicito, nunca o ponteiro publicado mais recente.
O cliente nao escolhe livremente o checksum de criacao; o servidor resolve a publicacao da classe selecionada.
Ausencia de publicacao e revisao publicada invalida sao estados diferentes; erro de integridade nao deve cair silenciosamente no catalogo mutavel.

Preservar `TbPersonagemClasse.ruleset` e o fallback de fichas antigas em `TbPersonagemCacador.ruleset`.
`views._hunter_ruleset_for_class` ja le ambos; apenas renomear essa funcao nao elimina a dependencia.
`views._resource_ruleset` rejeita revisoes conflitantes entre vinculos e perfis; manter essa verificacao.
`versioned_classes.resolved_classes` hidrata identidades congeladas e a habilidade permanente INT/SAB do perfil.
Nao substituir essa escolha pelo maior atributo, pelo padrao WIS ou por tags da classe viva.
Novos contratos podem usar capacidades declaradas; adaptadores antigos continuam selecionados por vinculo/revisao/contrato, nao pelo nome visivel.

## Magias: alcance exato das tags comuns agora

O leitor existente `_grants_de_tag`, chamado por `character_engine.magias_concedidas`, entende:
`spell_selection:<slug_em_snake_case>{always_prepared, extra, requires:lvl{N}}`.
Ele resolve o slug contra o catalogo selado, aceita a ponte underscore/hifen e recebe `class_level` da feature de classe/subclasse.
Assim, o desbloqueio usa nivel na classe de origem, nao nivel total da multiclasse; `VersionedClassCatalog.features` restringe a subclasse ativa.
`views._sync_magias_concedidas` materializa concessoes como `sempre_preparada`, com origem rastreada, e remove concessoes que sairam do conjunto pretendido.
Isso concede/prepara magias; nao implementa seus efeitos de combate nem transforma expansao de lista em concessao.

O pacote `home/content_packages/subclass_spell_sealed_plan_20261104.json` declara o alvo:
`95b5bdfb2f5bdec9d50cb42e0689bbd5e9643287a1b52ba6bd1be64c4376520d`.
Sao oito updates de features (PKs 1078, 1081, 1084, 1087, 1090, 1093, 1096, 1099), com dez tags cada: 80 ocorrencias, nao necessariamente 80 magias distintas.
Cobrem Alianca Selvagem, Crepusculo, Despertar, Enxame, Exorcistas, Exterminadores, Mutantes e Viajantes Primordiais, nos niveis 3/5/9/13/17.
O plano acrescenta primeiro `solo-sepulcral` ao spell-catalog e depois altera o class-catalog; nao reescreve revisoes anteriores.
Seu status local e `proposed_not_applied`; os 160 reader checks declarados nao comprovam criacao, ativacao ou equivalencia integrada em producao.

Essas 80 entradas podem ser resolvidas pelo leitor comum AGORA, quando presentes no snapshot efetivamente selecionado.
Porem `hunter_spells.grants_at` ainda le primeiro `hunter-rework.spell_grants`, antes das tags em `magias_concedidas`.
O conjunto local tem **83 entradas**: as 80 listas e tres concessoes adicionais:

| Concessao fora das 80 | Origem / desbloqueio | Limite da substituicao |
| --- | --- | --- |
| Hunter's Mark | Marca do Cacador / classe 1 | Pode receber tag comum de concessao; o rastreador de Marca continua necessario. |
| Battle Familiar | Companheiro Primordial / Alianca Selvagem 3 | Pode receber tag comum de concessao; nao substitui invocacao, bloco, PV ou comandos. |
| Mage Hand (`mao-arcana`) | Simbiose do Enxame / Enxame 3 | Pode receber tag comum na feature correta; nao esta entre os 80 updates. |

Tambem existe `hunter_traveler.final_grants`: escolhas persistidas de Caminho Final, nivel 18, fora dessas 83 entradas estaticas.
Nao apagar `granted_spells` inteiro ao substituir as listas. Manter os tres grants e Caminho Final ate haver dados e leitores equivalentes.
Suprimir fallback apenas para a familia coberta explicitamente pela revisao; nunca porque existe qualquer tag `spell_selection` ou porque o slug e `cacador`.
Na convivencia atual, o legado entra primeiro e `seen` deduplica por slug: pode esconder falha de cobertura/proveniencia das tags.
Comprovar a leitura das 80 tags sem esse fallback para essa familia, preservando as demais concessoes e a identidade dos slugs.
Nao mudar origem sem verificar a sincronizacao: ela atualiza origem e apaga concessoes ausentes; repetir a operacao deve manter o mesmo resultado.

## Mapa de substituicao e aposentadoria

Todos os caminhos abaixo sao relativos a `home/`. Aposentadoria refere-se ao consumidor substituido, nao a apagar snapshots antigos.

| Arquivo / ramificacao atual | Substituicao / limite | Criterio de aposentadoria |
| --- | --- | --- |
| `views.py`: `_criador_hunter_catalog_args`, `hunter_only`, `?hunter=1`, exclusao de Cacador, `_hunter_multiclass_publication` | Resolver e listar publicacoes por classe no criador e multiclasse comuns. | Mesmo catalogo em listagem, preview, create e multiclasse; checksum enviado pelo cliente nao muda a publicacao. |
| `bonfire/settings.py`, `hunter_publication_diagnostic.py`, `hunter_views.py`, mensagem em `admin.py` | Retirar dependencia operacional do setting; leitor comum do ponteiro. Fallback de configuracao nao e pin de ficha. | Todos os consumidores de ativacao usam publicacao comum; nenhuma atualizacao exige setting/restart. |
| `views.py`: pagina de classe e `legacy_hunter_presentation` | Ler apresentacao e progressao do snapshot publicado, como outras classes. | Tabelas, recursos e subclasses equivalentes; preservar apresentacao antiga enquanto seu contrato ainda for aceito. |
| `views.py`: `_hunter_ruleset_for_class`, `_resource_ruleset`; `versioned_classes.py` | Resolver vinculo de ficha por protocolo comum, com adaptador do perfil antigo. | Pin antigo, novo e conflito cobertos; nunca trocar pin por publicacao atual. |
| `views.py`: `_criador_resolver`, `_criador_persistir` e entrada de multiclasse com `hunter_ability` | Catalogo comum com capacidade de escolha permanente e adaptador de perfil. | Habilidade validada e persistida antes de grants/vitais; falha tardia reverte tudo; preview nao escreve. |
| `views.py`: `_pendencias_nivel`, `_lvl_aplicar_subclasse`; `hunter_preparation.py` | Subclasse por identidade congelada; conservar `hunter_order_replacements` para revisoes que o exigem. | Mapeamento de ordens, FK e desbloqueio preservados; nao selecionar equivalencia por sufixo/nome apenas. |
| `hunter_spells.py`, `character_engine.magias_concedidas` | Tags comuns para a familia das 80 listas; fallback granular para pins anteriores e grants restantes. | Cobertura exata por ordem/nivel sem fallback; tres grants e Caminho Final continuam disponiveis. |
| `hunter_spellcasting.py`, `spellcasting.py`, `views._classe_conjuracao` | `spellcasting` comum + `spell_limit` por recurso/tabela e slots `1o..5o` congelados. | Paridade dos 20 niveis, INT/SAB, slots, preparo e exclusao dos grants da quota; manter adaptador dos pins antigos. |
| `hunter_catalog.py` | Compositor de revisoes antigas, nao resolvedor universal. Conserva marcadores de replacement e dependencias. | Nova revisao declara semantica substituta completa; ferramentas e pins que leem marcadores continuam compativeis. |
| `hunter_regularization.py`, `hunter_views.py`, `models.TbPersonagemCacador` | Adaptador explicito de regularizacao/estado; nao remover por conter `hunter` no nome. | Migracao autorizada, versionada e verificavel de todos os campos/escolhas, sem perda de estado ou replay. |

## Debito residual por familia mecanica

Tags validas no vocabulario nao garantem execucao. O motor ja tem picks, recursos, passivas e estados genericos; faltam as ligacoes abaixo.

| Familia / arquivos | Lacuna concreta do motor compartilhado; preservar ate substituicao equivalente |
| --- | --- |
| Escolhas: `hunter_styles`, `hunter_masteries`, `hunter_expertise`, `hunter_choices`, `hunter_exterminator` | Falta contrato comum completo para troca de estilo uma vez por nivel, credito de maestria por descanso, expertise/favorecidos por progressao e escolhas alternativas de salvaguarda. Traduzir `hunter-*`, origem e payloads persistidos, nao apenas os rotulos. |
| Passivas: `hunter_passives`, `hunter_combat` | `base_passives.replaces` suprime tags antigas; ha aplicacao direta de ataques, saves fisicos, deslocamento, imunidades, sentidos e Crepusculo. Falta autoria unica declarada para substituicao, bonus aditivo de darkvision/iniciativa e save alternativo sem duplicar beneficios. |
| Enxame: `hunter_passives`, `hunter_swarm_combat` | Escalada/voo encadeados ao deslocamento, hover, protecao consciente e comandos condicionados a acerto/turno nao tem pipeline comum integrado equivalente. Ter `move`/`sense` generico nao aposenta essas regras. |
| Segredos/preparo/reacao: `hunter_rework`, `hunter_preparation`, `hunter_resources`, `hunter_reaction` | Falta contrato comum integrado para preparar exclusivos por ordem/nivel, custo aprimorado e confirmacao do gatilho com versao otimista. Ja usam `resource_engine.spend_resource`; isso nao migra a semantica nem as chaves `hunter:<id>:...`. |
| Marca: `hunter_mark` | Falta ciclo comum completo de presa, duracao de uma hora, incapacitacao acumulada, antecipacao/pistas, Inquisicao, Marca Mortuaria e Cacada Final. Morte da presa tambem recupera Despertar. Conceder a magia nao executa essas transicoes. |
| Companheiro: `hunter_companion` | Reutiliza `battle_familiar`, mas falta contrato comum integrado para persistir bloco/PV, custo de invocacao, acao/comando/sopro por turno, partilha de estado magico e acerto na presa marcada. |
| Despertar: `hunter_awakening` | Falta maquina comum integrada de ativacao/tempo/termino por inconsciencia, resgate a zero PV, PV temporarios e recuperacao por morte da presa/descanso. |
| Exorcistas/Lanterna: `hunter_exorcist`, `hunter_lantern` | Falta orquestrar atomicamente slots de circulos elegiveis, pontos, modos temporizados, frascos/cerimonias, alvos de expulsao e vinculo persistente do Santuario. Reset generico nao cobre essas transicoes. |
| Viajantes: `hunter_traveler` | Falta estado comum integrado de runa, distancia/plano, teleporte/Ruptura e Caminho Final: duas escolhas apos descanso, custo e uso por magia. `pick`/`cast` isolados nao leem `traveler.final_choices` nem preservam os usos. |
| Mutagenos: `hunter_mutagens` | Falta integrar aprendizado/preparo/consumo, efeitos e colaterais suprimiveis, transfusao/estigma na presa, quimera e regeneracao. Aplicacao ordenada altera atributos, defesas, checks e movimento; bloqueio de concentracao tambem e aplicado nos endpoints de magia. |

Em `character_engine.py`, manter ate migracao os hooks em `_resource_formula_context` e `_derive` para atributos de mutagenos;
`_maestrias_armas` para `hunter-mastery`; `_features_de_opcoes` para `hunter-style`; filtro de features substituidas, expertise e passivas;
e os hooks finais de defesas/movimento/checks de mutagenos. Retira-los muda calculo, nao apenas apresentacao.
Em `views.py`, manter a compatibilidade de preparo de magias com versao, bloqueios de concentracao e callbacks de descanso.
O descanso atual resolve inicialmente perfis Cacador, enquanto `_resource_ruleset` considera tambem pins comuns: alinhar os consumidores antes de declarar resolucao universal.

## Invariantes de aceite da migracao

- Pins legados sem perfil, pins com perfil antigo e novos pins comuns devem ter caminhos explicitos; publicacao nao regulariza fichas automaticamente.
- Revisoes com tags antigas apagadas por `hunter_catalog` continuam dependendo dos servicos substitutos e dos marcadores `hunter_*_replacement(s)`.
- Para as 80 listas: niveis imediatamente antes/no desbloqueio, oito ordens, multiclasse de nivel total alto/classe baixa, subclasse ausente e troca de origem.
- Para concessoes residuais: Marca, Battle Familiar, Mao Arcana e Caminho Final permanecem; repetir sync nao duplica nem remove indevidamente.
- Para mecanicas: manter autorizacao, lock, `expected_version`, `operation_id`/fingerprint, recursos gastos e eventos de descanso/termino ao trocar executor.
- Evidencias existentes: `test_subclass_spell_catalog`, `test_hunter_spells`, `test_creator_pinned_catalog`, `test_creator_hunter_binding`, `test_hunter_multiclass_ruleset` e testes focados por familia. Nao equivalem a aceite integrado desta migracao.
- Evidencia estatica confirmada: JSON com oito features/80 tags no formato comum; nao confundir essa contagem com execucao de testes ou ativacao da revisao.

Conclusao: unificar entrada/publicacao e preferir tags comuns onde ha cobertura comprovada; conservar adaptadores versionados do restante.
Apagar tudo por prefixo `hunter`, retirar o perfil ou apenas renomear variaveis nao constitui unificacao mecanica.
