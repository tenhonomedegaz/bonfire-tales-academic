# Magias De Subclasse: Proxima Entrega Prioritaria

Pedido do PO recebido em 04/11/2026; **48 subclasses aplicadas e relidas na
producao; oito Ordens conferidas, com uma magia ausente do catalogo pinado**.
L1-L5 do laboratorio entregues. Esta frente precede novas mecanicas do VTT.

## Estado Objetivo

- Referencia estruturada: 595 ocorrencias de concessao, 56 subclasses, sete classes;
  48 entradas de variantes e oito universais. Nao sao 595 magias diferentes.
- Consulta autorizada por API da producao: 582 identidades de magia paginadas apos o novo cadastro,
  somente PK/slug/nomes/nivel/classes_slugs, sem dump de jogadores/banco.
- 595 referencias resolvidas para 280 magias distintas. Seis equivalencias
  revisadas estao em dados explicitos com slug/circulo esperado; sem fuzzy match
  silencioso nem correcao global de metadados da producao.
- Nenhuma identidade de magia pendente. O PO confirmou Branding Smite -> Shining
  Smite e forneceu a referencia completa de Grave Ground (AU p.40). Solo Sepulcral
  foi traduzido, criado pela API na producao (PK 583) e relido com todos os campos
  conferidos. Cobertura e
  limites mecanicos da nova magia: `docs/vtt/grave-ground.md`.
- A API instalada lista classe/subclasse/habilidades e permite CREATE/PATCH
  restrito, com If-Match, idempotencia e relacoes somente no CREATE. A consulta
  inicial nao enxergava a publicacao legada selecionada por configuracao; a
  correcao generica acrescenta `mode:configured`, sem mudar o catalogo lido.
- Pacote portavel de 56 definicoes em
  `home/content_packages/subclass_spell_tags_20261104.json`; e a definicao
  desejada integral, nao um recibo de publicacao das 56 subclasses.
  Reconciliacao em `docs/vtt/subclass-spells-resolution.json`.
- Aplicadas na producao: 17 atualizacoes e 31 criacoes para Artifice, Clerigo,
  Druida, Feiticeiro, Mistico e Paladino (48 subclasses). Cada registro teve copia
  anterior, UUID de idempotencia e releitura integral dos campos alterados.
  Nenhuma ficha foi gravada. Dezenove declaracoes antigas de concessao foram
  substituidas exatamente, preservando todos os efeitos nao relacionados.
- Nomes mecanicos usam snake_case; slugs de catalogo continuam hifenados e o
  leitor existente faz a ponte. Validador estrito aplicado ao pacote inteiro;
  a tentativa anterior hifenada foi recusada pela API antes de gravar conteudo.
- As oito Ordens novas foram conciliadas por slugs `*-rework` em dados explicitos.
  As seis Ordens legadas nao receberam alteracoes. A API inicial retornou fonte
  porque nao ha ponteiro geral: a publicacao do Cacador ainda vem da configuracao
  antiga. A consulta corrigida confirmou a revisao `da099956cb1a...`; suas 80
  concessoes ja existem em `hunter-rework` (mais tres beneficios extras).
- A divergencia concreta e Solo Sepulcral: existe na fonte viva (PK 583), mas
  falta em `spell-catalog` dessa revisao. O leitor recusa Exorcistas nos niveis
  17-20. Nao duplicar as tabelas nem alterar snapshots existentes para contornar.
  Plano aditivo e ensaio: `docs/vtt/sealed-spell-supplement.md`.
- A concessao por `requires:lvl{N}` em habilidade de classe/subclasse agora usa
  o nivel da classe-fonte. Fontes sem classe conservam nivel total. Nao alterou
  o calculo geral de nivel ou efeitos por talento.
- Export v1.3 adiciona `acesso_magias`: uniao readonly do aprendizado persistido
  com concessoes ativas, com identidade, preparo, fontes, tags e revisao. A lista
  antiga `magias` continua intacta. Revisao vinculada invalida/ambigua nao cai no
  catalogo atual. Nao houve escrita/sync escondido no export.
- Laboratorio mostra as magias da copia e seu preparo. Tags de magia nao entram
  automaticamente nas passivas do ator nem viram ataque generico. Este trabalho
  **nao implementa todo o executor de conjuracao**, alcance, concentracao ou upcast.

## Fonte E Limites

Lista integral: [Referencia do PO](references/subclass-spells-user-20261104.txt).
E dado de conteudo, nao codigo executavel nem prova do estado atual do catalogo.
Preservar nomes ingleses para resolver identidade; portugues possui sinonimos,
erros de digitacao e divergencias. Nao adivinhar PK/slug a partir da traducao.

Inclui Artifice, Cacador, Clerigo, Druida, Feiticeiro, Mistico e Paladino,
com escolhas ramificadas (Pastoreio Elemental e Genio), magias universais e niveis
de classe distintos do circulo da magia. Druida da Terra foi explicitamente
adiado pelo PO. Nao inventar sua lista nem normalizar niveis por tabela externa.

Exemplos que exigem conferir catalogo/referencia, nao publicacao cega:
`Wall of Wind`/`Wind Wall`, `Represalia Infernal [Inflict Wounds]`,
`leomond's tiny hut` e nomes homebrew/TCM. Preservar o original e registrar
resolucao ou pendencia por entrada; nao criar duplicatas de magia por traducao.

## Reaproveitamento Confirmado No Codigo

| Arquivo / ponto | Responsabilidade e mudanca esperada |
| --- | --- |
| `home/character_engine.py`: `magias_concedidas`, `_grants_de_tag` | Ja distingue concessao de ampliacao de lista e le fontes taggeadas. Auditar cobertura de niveis de classe e ramos; corrigir leitor generico apenas se faltar suporte |
| `home/spellcasting.py`: `character_spell_list_delta`, `class_spellcasting_contract` | Lista efetiva/contrato por classe; `modify:spellcasting{list}.add/remove{spell:...}` nao concede nem prepara sozinho |
| `home/views.py`: `_sync_magias_concedidas` | Materializa concessoes no fluxo autorizado da ficha; conferir idempotencia, origem e legados, nao chamar ao ler/exportar uma cena |
| `home/pathbuilder.py` | Ja chama sincronizacao; conferir criacao/avanco/troca de subclasse conforme fluxo existente |
| `home/management/commands/export_personagem_vtt.py`: `_magias` | Hoje le relacao persistida e exporta PK/nome/circulo/origem/preparada. Verificar lacunas de proveniencia, acesso e tags antes de ampliar contrato aditivamente |
| `home/vtt_lab_sources.py`, `home/vtt_lab.py` | Projetar somente magias autorizadas com fonte e contexto seguros; biblioteca e snapshot pinados, leitura sem escrita na ficha |
| `home/vtt_lab_resources.py`, `home/vtt_lab_combat.py` | Conjuracao futura deve validar acesso, preparo quando exigido, slot/recurso e custo atomicamente; ataque/cura declarados atuais nao provam acesso a uma magia |
| `docs/criador-personagem/dicionario-tags.md` | Documentar semantica real suportada e exemplos de dados; nao introduzir sintaxe sem leitor e teste |

Ja existem `cast{... always_prepared ...}` e `spell_selection`/`spell` concretos
no leitor de concessoes. A sintaxe final deve ser validada pelo parser e leitores
reais, com fonte/nivel corretos. Nao criar outro sistema exclusivo de subclasses.
**Ter uma magia na lista nao significa conhece-la, prepara-la ou poder conjura-la
gratuitamente.** Nao marcar todas como always_prepared sem conferir a regra de
concessao da habilidade de origem.

## Sequencia Finita

1. Inventariar via API de leitura os registros relevantes de classe/subclasse,
   habilidades, tags, magias e revisoes. Consultas filtradas/paginadas; sem dump
   integral, sem alterar producao para descobrir o que existe. Distinguir legado
   da versao corrente e preservar PKs. Esta consulta ainda nao foi executada.
2. Montar manifesto estruturado por classe/subclasse/habilidade, nivel de classe,
   identidade canonica da magia, tipo de concessao e escolha condicional. Separar
   resolvidos, ja corretos, divergentes e nao encontrados. Nao inferir identidade
   por nome aproximado; nao traduzir PT para um slug sem verificar o catalogo.
3. Confrontar manifesto com tags atuais e provar amostra pequena no leitor:
   antes/no/depois do nivel, multiclasse, ramo escolhido e universal. Adicionar
   operacao generica so se nenhuma tag existente expressar a regra. Nenhuma
   migration por subclasse; alteracoes de conteudo sao dados via API/admin.
4. Ajustar sincronizacao/derive somente na lacuna demonstrada. Rodar a mesma
   concessao duas vezes nao duplica, trocar ramo nao remove magia aprendida por
   outra fonte, ficha legada preserva sua revisao. Niveis de classe nao podem
   virar nivel total por acidente.
5. Exportar identidade, fonte e disponibilidade efetivas para o laboratorio.
   Testar com magias existentes e tags reais; recusar contexto/custo nao resolvido.
   VTT nao escreve `personagem.magias`, nem executa sync escondido no GET/export.
6. Prova ponta a ponta focada (ficha -> export -> sessao -> comando suportado),
   comparar esperado/observado e listar o que segue manual. Publicar somente o
   lote resolvido, com previa/diff/recibo pela API e sem sobrescrever dados do
   jogador. Commit/push/deploy e alteracao de producao continuam etapas explicitas,
   nao foram executadas como parte deste planejamento.

Sem ampliar para iniciativa, concentracao completa, todas as magias ou 3D para
fechar essa entrega. Enquanto a lista nao estiver reconciliada, nao anunciar
"magias de todas as subclasses implementadas".

## Aceite E Testes Pontuais

- Dados: cada entrada com destino canonico/nivel/fonte, ou pendencia especifica;
  sem duplicatas editoriais. Ramificacoes nao concedem todas as colunas de uma vez.
- Ficha: concessao e acesso corretos no limiar por classe, nao por nivel total;
  escolhas, magias fora da lista-base, sempre-preparadas quando devido e legados.
- Motor: alterar a tag de teste altera resultado sem mudar codigo por nome;
  ampliar lista nao concede uma escolha pronta; nenhum cast gratuito implicito.
- VTT: snapshot readonly apresenta a mesma disponibilidade, origem e revisao;
  reenvio nao duplica uso/custo; magia nao autorizada e recusada. Efeitos sem
  executor suportado ficam explicitamente manuais, nao sucesso silencioso.
- Reutilizar `home/test_spellcasting_contracts.py`, `home/test_versioned_spellcasting.py`,
  `home/test_versioned_spell_sheet.py`, `home/test_versioned_sync.py`,
  `home/test_export_personagem_vtt.py` e testes focados do laboratorio, ampliando
  casos nos pontos realmente alterados. Nao rodar banco configurado por padrao:
  identificar banco local seguro ou usar SQLite temporario isolado.

## Arquivos Entregues E Conferencia

| Arquivo | Funcao |
| --- | --- |
| `home/content_packages/subclass_spells_20261104.json` | Referencia integral estruturada e niveis originais |
| `home/content_packages/subclass_spell_identity_overrides_20261104.json` | Equivalencias canonicas revisadas como dados |
| `home/content_packages/subclass_spell_target_bindings_20261104.json` | Destinos e variaveis de escolha explicitos |
| `home/content_packages/subclass_spell_tags_20261104.json` | 56 definicoes portaveis sem PKs impostas |
| `home/subclass_spell_catalog.py`, `tools/plan_subclass_spells.py` | Reconciliacao e compilacao de tags existentes, sem escrita em banco |
| `home/character_engine.py` | Gate da concessao por nivel da classe-fonte |
| `home/vtt_spell_access.py`, exportador existente | Projecao readonly do acesso efetivo, tags opacas e proveniencia |
| `home/db_access.py` | Leitura de catalogo de classes e CRUD restrito de habilidades |
| Template/JS do laboratorio | Consulta de magias da copia, sem botao de cast indiscriminado |

Tags geradas usam `spell_selection:<nome_snake_case>{always_prepared, extra, requires:lvl{N}}`.
Variantes usam `match(pick:<variavel>){valor:{...}}`; sem escolha, nao ganham todos
os ramos. Nao foi criado dispatch por nome de magia/classe/subclasse. As regras
especificas de cada magia continuam em suas tags cadastradas.

Passaram testes puros de toda referencia resolvida e seus limiares, testes reais
em SQLite temporario de multiclasse/sync/repeticao/preservacao de aprendizado,
leitura readonly e revisao antiga apos edicao atual; testes focados de API e export.
Playwright executou 25 fluxos desktop/mobile sem pageErrors; capturas
`docs/vtt/qa/spells-desktop.png` e `spells-mobile.png`. Nenhum teste carregou
bonfire.settings/.env ou acessou PostgreSQL configurado.

## Falta Para Concluir

1. Instalar `spell-catalog-revision` e sua previa pelo `/site-update`; a consulta
   de snapshots configurados ja foi instalada e conferida. As 48 subclasses
   acima ja estao gravadas; nao reaplicar seus CREATEs. Nao ha nova migration.
2. Aplicar o suplemento de uma magia na revisao ativa apos previa/ETag. Criar a
   revisao de classe com as tags das oito fontes existentes; sem linhas-fonte
   novas, remocoes ou troca de apresentacao.
   `tools/plan_subclass_spells.py --source-catalog <json>` aceita colecoes
   `classes`, `subclasses`, `features`. `--source-fixture` serve so ao ensaio local.
   PK advisory do plano nao autoriza sobrescrever PK de producao. Reler detalhe
   e comparar tags/ETag antes de CREATE/PATCH, guardar antes e preservar outros efeitos.
3. Confirmar os checksums antes de ativar o novo ruleset. Nao criar cards duplicados. As duas
   identidades antes pendentes ja foram resolvidas; nao pedir novamente suas
   referencias. Nao remover conteudo por ausencia de uma entrada.
4. A ativacao atual e por configuracao legada, nao por ponteiro comum. Trocar o
   checksum/reiniciar no fluxo monitorado somente apos o alvo existir. Nao forcar
   `presentation_source:catalog`: isso muda o contrato visual. Fichas ja pinadas
   conservam a revisao; sua atualizacao requer um fluxo proprio, nao reatribuicao
   em massa ou afirmacao de que a criacao da revisao ja as corrigiu.

O fixture principal, classes, subclasses e personagens nao foram alterados.
As escritas foram Solo Sepulcral e 48 fontes de concessao via API. Recibos e
copias anteriores ficam protegidos localmente em
`AmandaBot/scratch/subclass-spells-20261104/grants-backup` e `grants-receipts`.
`docs/vtt/subclass-spells-tag-plan.json` e um plano de referencia antes da
aplicacao, nao evidencia de que o Cacador foi publicado. Nao anunciar 56/56 antes disso.
O VTT pode avancar localmente enquanto depende desse deploy.

Consulta adicional: `POST operations/class-catalog-read/` le a revisao publicada
por classe e secao, com `mode` e `ruleset_checksum`. Sem publicacao usa fonte;
publicacao invalida recusa a leitura, sem fallback. Usar essa consulta para
conciliar subclasses do Cacador atual antes de planejar escritas na fonte.
Contrato completo em `docs/catalog_api.md`. O fixture antigo nao autoriza criar
novas subclasses nem sobrescrever identidades da producao.
