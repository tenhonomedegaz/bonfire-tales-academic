# Laboratorio VTT 2D Python

Atualizado: 04/11/2026. Estado: **L1-L5 implementados localmente; envio autorizado para dev**.
O VTT completo e a validacao automatica de combate ainda nao estao concluidos.

## 1. O que esta pronto

- Entrada por link direto `/vtt/laboratorio/`, sem menu, sitemap ou anuncio.
- Feature flag `VTT_LAB_ENABLED`, desligada por padrao. Conta ativa e superuser
  obrigatorios em todas as rotas; `is_staff` sozinho nao concede acesso.
- Sessoes individuais por admin, salvas em tabelas proprias. Outro admin nao
  acessa uma sessao apenas por conhecer seu UUID.
- Importacao pelo ID real do personagem usando **a mesma** funcao
  `exportar_personagem` da CLI existente. Nao ha derivacao alternativa em JS.
- Copia com PK de origem, hash do export e snapshot para inspecao. PV inicial
  vem do estado neutro do exportador, nao de uma sessao de campanha em andamento.
- Camera ortografica, grade, retrato/token, selecao por clique, pan, zoom,
  enquadramento e destino por clique reaproveitados do renderer Three.js do VTT.
- Posicao XYZ, ajuste manual de PV, contador manual de turno e registro recente.
- Importacao de criatura por PK do bestiario, com HP fixo do statblock (ou campo
  numerico). Criaturas que escalam com dono exigem contexto e sao recusadas neste
  recorte; formulas de HP nao sao adivinhadas.
- Combate por `CombatEncounter`, o executor Python existente: escolher equipes,
  iniciar/encerrar turnos, declarar acerto/dano e cura. Defesas e condicoes
  suportadas pelo motor sao lidas das tags originais, nao do nome da criatura,
  classe, talento ou descricao em texto.
- Vocabulario e fontes ficam congelados no inicio do combate; replay limitado
  preserva PV, condicoes e uso da acao ao recarregar. Tipos de dano da interface
  vem do catalogo da biblioteca, nao de uma lista paralela no frontend.
- Revisao otimista + transacao + recibo unico por comando: uma repeticao exata
  nao reaplica a operacao; uma aba atrasada recebe 409 e recarrega o estado.
- Recursos exportados viram pools da copia de laboratorio, inicialmente cheios,
  mantendo `id_fonte` e aliases canonicos. `resource_cost` incondicional, simples
  ou com quantidade inteira/formula resolvida, debita junto do ataque, mesmo em
  miss. Saldo insuficiente ou custo ambiguo/nao suportado recusa a acao sem dano,
  gasto de acao ou alteracao parcial. Reenviar o mesmo UUID nao cobra novamente.
- Regua 3D no servidor, somente leitura, com as quatro metricas do VTT existente.
  Os calculos Python foram comparados diretamente com o codigo TS original.
- Deslocamento numerico adicional no derive/export v1.2: base legada validada
  mais bonus numerico final ja calculado pelo motor; modos desconhecidos geram
  aviso, nunca velocidade presumida. Criaturas usam o speed estruturado.
- Export v1.3: acesso efetivo de magias em bloco aditivo, com fontes, preparo,
  tags e proveniencia do catalogo. Uniao readonly de magias persistidas e
  concessoes ativas, sem sincronizacao oculta. Consulta no inspetor da copia;
  nao converte tags de uma magia em passiva global ou cast livre. Detalhes e
  estado do pacote de subclasses em `docs/vtt/subclass-spells-plan.md`.
- Editor de celulas normais, dificeis e bloqueadas fora do combate. Terreno,
  ocupantes e velocidades sao congelados ao iniciar; previa de caminhada somente
  leitura e confirmacao validada novamente no servidor. Gasto acumulado por turno,
  independente do uso da acao, preservado pelo replay e pelos recibos.
- Frontend responsivo; renderer carregado apenas ao abrir uma sessao, sem host,
  interpretador ou motor de regras TypeScript. Render limitado a 30 fps e pausado
  quando a aba esta oculta.
- L5: imagem de mapa com calibracao por pixels/celula, origem X/Y, opacidade da
  imagem e da grade. Usa a camada de fundo do renderer existente; metadados de
  apresentacao nao alteram terreno, distancia ou custo de movimento.

**Cobertura parcial, nao uma automacao completa do sistema.** Caminhada automatica
limitada a quatro direcoes, piso Z=0 e tokens de uma celula; nao valida alcance
de ataques, LoS, voo, escalada ou terrenos em andares. Qualquer condicao ativa
deixa o movimento para adjudicacao manual nesta versao, sem regra por nome.
Acerto, dano rolado, cura e ordem de turno sao declarados pelo admin.
O ajuste avulso de PV continua manual e nao equivale a executar uma habilidade.
Durante combate ativo, esse ajuste, importacoes, movimento manual, edicao do
terreno e contador avulso ficam bloqueados
para nao divergirem do replay. O saldo manual dos recursos tambem fica bloqueado
durante combate. Cura declarada nao comprova que o ator conhece uma
magia, tem alcance ou pagou seu recurso; isso ainda e adjudicacao manual da mesa.

## 2. Autoridade e seguranca

Python/Django decide comandos e persistencia. O navegador apenas apresenta o
estado confirmado. Nenhum segredo da API de banco e entregue ao cliente.
POST exige CSRF. Respostas privadas usam no-store; cada chamada revalida acesso.
As tabelas de personagens, inventario, ouro, progresso e catalogo nao recebem
updates desta ferramenta. O export roda sob um bloqueio de escritas na conexao
padrao e falha fechado se um helper tentar gravar, mesmo engolindo a excecao.

Limites atuais: corpo 16 KiB; export individual 256 KiB; estado 2 MiB; 128 tokens;
100 eventos recentes; coordenadas inteiras dentro da grade 24 x 18, z 0..100.
Recibos persistentes guardam hash/revisao, nao outra copia integral da ficha.
Combate: ate 32 participantes e 256 comandos de dominio (ultimo slot reservado
para encerramento manual), biblioteca ate 512 KiB. O snapshot inicial e o journal
permitem reconstruir o executor existente sem persistir seus campos privados.
Um hash dos fontes relevantes do motor/adaptador impede replay silencioso apos
alteracao de codigo. Nao ha migracao automatica de combate antigo entre motores:
preservar a sessao anterior e criar outra copia para testar a versao nova.
Pools usam ate 128 entradas e 64 KiB; saldo e maximo sao inteiros entre zero e
1.000.000. Somente `canonical_key` do servico de recursos e reutilizado: nenhum
mutador do ledger oficial e chamado. Export de pool malformado nao impede abrir
a ficha: resulta em aviso e pools indisponiveis; uma acao com custo nao resolvido
continua recusada, nao gratuita. Reset e metadado, nao descanso automatizado.

As tabelas de laboratorio podem entrar em backups gerais ja que sao modelos do
site. Validar politica de retencao antes de uso prolongado; nao prometer historico
integral de replay a partir dos 100 eventos recentes.

## 3. Arquivos e manutencao

| Arquivo | Responsabilidade |
| --- | --- |
| `home/vtt_lab.py` | Gate, HTTP, import readonly, validacao generica, revisao e comandos |
| `home/vtt_lab_sources.py` | Projecao conservadora de fontes reais: PKs, tags e contexto por acao; sem inferir mecanica de prosa |
| `home/vtt_lab_combat.py` | Adaptador do CombatEncounter, snapshot, biblioteca pinada e replay limitado; nenhuma regra por nome |
| `home/vtt_lab_resources.py` | Custos via parser/operacoes existentes, aliases, limites, debito e validacao de saldo |
| `home/vtt_lab_spatial.py` | Port fiel de distance.ts para Python; footprints, quatro metricas e conversao de escala |
| `home/movement_contract.py` | Projecao numerica compartilhada, sem interpretar prosa final nem reexecutar tags |
| `home/character_engine.py`, `home/management/commands/export_personagem_vtt.py` | Adicao de movimento ao derive e export v1.2; preserva campos anteriores |
| `home/vtt_lab_movement.py` | Validacao do mapa e contrato, ocupacao, budget e caminho ponderado NetworkX |
| `requirements.txt` | NetworkX 3.7, importado sob demanda no calculo de caminhos |
| `home/vtt_lab_models.py` | `VttLabSession`, `VttLabReceipt`, estado inicial |
| `home/models.py` | Registro dos dois modelos no app Django |
| `home/migrations/0167_vtt_lab.py` | Somente schema: duas tabelas novas, indice e unicidade; nenhum dado por classe/talento |
| `home/urls.py` | Seis caminhos privados abaixo; lista e criacao compartilham URL |
| `bonfire/settings.py` | Flag desligada por padrao |
| `home/templates/home/vtt_lab.html` | Mesa isolada, sem processadores sociais/propagandas |
| `home/static/js/vtt-lab.js` | Interacao, chamadas same-origin, conflito de revisao e selecao |
| `home/static/css/pages/vtt-lab.css` | Layout operacional desktop/mobile |
| `home/static/vtt/renderer.js` | Artefato visual gerado; nao editar manualmente |
| `home/static/vtt/renderer.manifest.json` | SHA-256 do bundle e de cada entrada de build |
| `tools/build_vtt_lab.mjs` | Build visual restrito, sem core/net/ref; copia licenca Three.js |
| VTT: `apps/client/src/siteLabRenderer.ts` | Adaptador fino para SceneWorld, TopDownMode e Picker existentes |
| `home/test_vtt_lab.py` | Testes de contrato, seguranca e persistencia isolados |
| `home/test_vtt_lab_sources.py`, `home/test_vtt_lab_combat.py` | Contratos de fonte e executor puro sem banco |
| `home/test_vtt_lab_resources.py`, `home/test_vtt_lab_spatial.py` | Custos atomicos e contratos de medida |
| `home/test_movement_contract.py`, `home/test_vtt_lab_movement.py` | Export numerico, ocupacao, custo e limites da caminhada |
| `tools/check_vtt_spatial_parity.mjs` | Compara Python com o modulo TS real; nao instala outro motor no servidor |
| `home/js_tests/vtt_lab_fixture.py` | Demonstracao loopback, admin/dados ficticios, SQLite em memoria |
| `home/js_tests/vtt_lab.e2e.cjs` | Fluxo real de navegador contra a demonstracao; inicia e encerra o servidor |

O build nao consolida nem sobrescreve o grande WIP do repositorio VTT. Manifest
registra os 75 arquivos realmente usados; nao significa que os demais foram
revisados. Nao copiar o repositorio inteiro, node_modules ou referencias para o
site. O bundle visual L5 tem 837.718 bytes antes de compressao HTTP.

Reconstruir o bundle visual:

```powershell
node tools/build_vtt_lab.mjs "C:/caminho/bonfire-vtt"
```

O caminho e opcional se os dois repositorios forem irmaos. Usar as dependencias
instaladas do VTT; nenhuma instalacao Node adicional e necessaria no servidor de
producao para servir o bundle ja gerado.

## 4. Contrato HTTP

| Metodo / rota | Resultado |
| --- | --- |
| GET `/vtt/laboratorio/` | Entrada protegida |
| GET `/vtt/laboratorio/api/sessoes/` | `{sessions:[{id,nome,revision,updated_at}]}`, sem snapshots |
| POST na mesma rota | Cria com `{nome, personagem_id?}`; retorna envelope |
| GET `/vtt/laboratorio/api/sessoes/<uuid>/` | Envelope `{id,nome,revision,state,updated_at}` |
| GET `/vtt/laboratorio/api/sessoes/<uuid>/medir/?origin_id=...&target_id=...` | Medida dos tokens da propria mesa, sem salvar ou incrementar revisao |
| GET `/vtt/laboratorio/api/sessoes/<uuid>/caminho/?x=...&y=...&z=0` | `{actor_id,path,cost_units,remaining_units,revision}`; somente leitura, turno ativo |
| POST `/vtt/laboratorio/api/sessoes/<uuid>/comandos/` | Aplica comando e retorna envelope |

Comandos usam JSON com `command_id` UUID, `expected_revision` inteiro, `type` e:

- `import_character`: `personagem_id` inteiro positivo.
- `move_token`: `token_id` UUID, `x`, `y`, `z` inteiros.
- `configure_board`: `blocked_cells:[{x,y}]`, `terrain_cells:{"x,y":"difficult"}`;
  somente fora do combate. Normal pode ser omitido; obstaculo sobre token e recusado.
- `combat_move`: `x`, `y`, `z:0`; ator e custo vem do turno e mapa pinados, nunca
  de valores enviados pelo cliente. Nao usa acao; nao confundir com move_token manual.
- `set_hp`: `token_id` UUID, `hp` inteiro entre zero e maximo da copia.
- `set_resource`: `token_id`, `resource_id` importado, `current` inteiro no teto;
  ajuste de teste permitido somente fora de combate, nao operacao na ficha oficial.
- `next_turn`: nenhum campo adicional.
- `import_creature`: `criatura_id` inteiro positivo, somente fora do combate.
- `combat_start`: `teams` mapeando UUIDs dos tokens para equipes; minimo duas
  equipes, participantes vivos e com fontes importadas nesta versao.
- `combat_start_turn`: `actor_id` UUID; identidade sequencial do turno gerada pelo
  servidor. Repetir UUID de requisicao nao abre outro turno.
- `combat_attack`: `target_id`, `action_id` da fonte do ator, `hit` booleano,
  `damage` inteiro declarado e `damage_type` da biblioteca pinada. Nenhuma tag
  arbitraria pode ser inserida pelo cliente neste comando.
- `combat_heal`: `target_id`, `amount` inteiro declarado.
- `combat_end_turn`, `combat_end`: sem outros campos.

Valores declarados de dano/cura aceitam 0..1.000.000, sem bool/float. O motor
existente determina consumo de acao, resistencias/imunidades e condicoes que
suporta. Fontes sem contexto resolvivel, escolhas ambiguas ou gates pendentes
geram aviso `partial` e nao ganham automacao presumida. Programa misto fica
inteiro na acao; nao e achatado como uma passiva global. Sem acao taggeada util,
ha `manual` para um ataque declarado sem efeitos inventados.

Campo opcional `state.combat`: snapshot inicial, `library_raw`, `library_hash`,
`engine_revision`, `journal`, `view`, estado de encerramento e ultimo resultado.
`view` projeta ator/acao disponivel, PV/PV temporarios, equipes, condicoes,
eventos recentes e tipos de dano. `state.combat_vocabulary` registra origem e ID
da revisao do vocabulario. Regras da fonte tambem ficam em `token.rules` para
inspecao; o combate usa a copia inicial, nao atualiza do catalogo ao recarregar.
`token.resources` e `combat.view.resources[actor_id]` guardam os saldos da copia.
Custos vem das tags da acao selecionada, nunca de um valor de custo enviado pelo
browser. Alias ambiguo, alternativa/faixa, custo condicional/opaco, `uses` ou
`resource_restore` ainda nao executaveis sao recusados explicitamente.

Regua retorna `metric`, `units`, `units_per_cell`, `cells`, `meters`, `revision`,
origem/alvo e flags `path_validated=false`/`line_of_sight_validated=false`.
`board.metric` seleciona a metrica, `board.cell_meters` a escala. O padrao do lab e
manhattan3d/1,5 m, como o perfil inspecionado do VTT. Tokens atuais sao unitarios;
o helper ja suporta `size_cells` mas o importador/render ainda nao definem tamanhos
reais de criaturas. A regua nao autoriza ataques nem valida deslocamento/LoS.

Campos extras sao recusados. Erros de negocio: `{error,message}`; 403 acesso/CSRF,
404 flag desligada ou registro nao encontrado, 409 conflito, 413 tamanho,
422 export impossivel, 503 falha de banco. Middleware global pode devolver seu
proprio formato de erro; o frontend conserva o status mesmo sem JSON.

Reenviar **o mesmo payload e UUID** verifica o recibo antes da revisao e devolve o
estado atual com `X-VTT-Lab-Replayed: true`. Reutilizar UUID com payload diferente
e conflito. A criacao de sessao nao tem nonce idempotente nesta primeira versao;
apos timeout, conferir a lista antes de criar novamente.

## 5. Conferencia realizada

- 31 testes HTTP/backend em SQLite **somente em memoria**, incluindo esquema novo,
  permissao/flag/CSRF, dono, import, limite, rollback, recibos e leitura oficial.
- 107 testes puros das fontes/adaptador/recursos/medida/movimento: biblioteca real sem banco,
  resistencia/imunidade, condicao e bloqueio de cura, contexto por acao,
  limites, journal adulterado, versao do motor, contorno de obstaculos, aliados,
  inimigos, terreno dificil, budget exato, snapshot e reset por turno. Eles nao substituem a prova de
  conteudo real da campanha que ainda falta fazer no ambiente local identificado.
- Navegador Edge/Playwright: criar, importar ficha ficticia, alterar PV, mover,
  recarregar, conflito entre abas, destino por clique, zoom e viewport mobile;
  depois importar criatura, iniciar combate/turno, ataque com `resist:fogo`
  (dano declarado 5 resulta em 2), reabrir sem recuperar acao gasta, curar e encerrar.
  Tambem: gastar dois usos (2 -> 1 -> 0), recarregar, rejeitar terceira tentativa
  sem dano/gasto de acao, medir sem gravar e ajustar saldo somente fora de combate.
  L4: editar terreno, prever rota ponderada sem gravar, confirmar caminhada e
  descontar seis celulas sem consumir acao; 24 fluxos, nenhum erro de pagina.
- Paridade espacial: 128 casos comparados com `packages/spatial/src/distance.ts`
  real, incluindo altura, footprints e as quatro metricas. Nao e teste de caminho.
- Nenhum erro de pagina. Capturas em `docs/vtt/qa/lab-desktop.png` e
  `lab-mobile.png`; canvas separado para detectar branco/vazio em ambos tamanhos.
  Combate: `combat-desktop.png` e `combat-mobile.png` na mesma pasta.
  Recursos/regua: `resources-desktop.png` e `resources-mobile.png`.
  Caminhada: `movement-preview.png`, `movement-desktop.png`, `movement-mobile.png`.
- A funcao real de export e chamada pelo adaptador; o teste desta funcao isola
  derivacao/dependencias. **Nao foi feita importacao de personagem de producao.**
- Nao foram carregados bonfire.settings/.env nos testes, aplicadas migrations em
  banco configurado ou modificados dados de producao. Concorrencia com bloqueio
  de linha usa `select_for_update`, mas ainda falta evidencia concorrente no
  PostgreSQL real de desenvolvimento; SQLite nao prova esse bloqueio.

Executar somente os testes focados:

```powershell
py -3.14 -m home.test_vtt_lab --isolated
py -3.14 -m unittest home.test_vtt_lab_sources home.test_vtt_lab_resources home.test_vtt_lab_combat home.test_vtt_lab_spatial
py -3.14 -m unittest home.test_movement_contract home.test_vtt_lab_movement
node tools/check_vtt_spatial_parity.mjs
node home/js_tests/vtt_lab.e2e.cjs
```

Demonstracao independente, sem login real nem banco do projeto:

```powershell
py -3.14 home/js_tests/vtt_lab_fixture.py --port 8901
```

Abrir `http://127.0.0.1:8901/vtt/laboratorio/` e importar personagem ID **1** e
criatura ID **1**. A criatura ficticia declara resistencia a fogo nas tags reais
consumidas pelo motor, para testar reducao de dano. Todos os dados
somem ao encerrar o processo. O admin automatico existe **somente neste fixture**,
cujo servidor escuta exclusivamente no loopback; nunca configurar este modulo
como aplicacao de producao.

## 6. Proxima rodada finita

**Prioridade nova do PO:** concessao de magias de subclasse e acesso efetivo por
classe, compartilhados por ficha e VTT, antes de ampliar outras mecanicas.
Plano finito e referencia integral: `docs/vtt/subclass-spells-plan.md`.
Relatos sociais a executar separadamente: `docs/qa/20261104-perfis-e-magias.md`.

1. Confirmar banco **local** de desenvolvimento antes de aplicar `0167`; conferir
   uma ficha real e proveniencia de ruleset/vocabulario. O .env local foi descrito
   como igual ao de producao: nao presumir que executar manage.py e seguro.
2. Conferir uma criatura e habilidade **reais do banco local** no fluxo implementado;
   expandir condicoes/duracao escolhidas conforme fontes concretas. Importador e
   adaptador Python ja existem; nao reiniciar outra implementacao. Nao publicar
   todo o pack historico como atual nem remover avisos de cobertura parcial.
3. Melhorar diagnostico de cobertura: distinguir efeitos aceitos pelo executor,
   operacoes apenas declaradas e fontes excluidas por contexto; o simples fato de
   uma acao ter tags nao significa que todos os seus efeitos foram automatizados.
4. Expandir custos somente pelos contratos reais necessarios (alternativas,
   escolha de quantidade, restauracao e conjuracao), conservando recusa explicita
   onde faltar suporte. Pools e custo incondicional atomico ja estao implementados;
   nao rederivar bonus que ja vieram de `character_engine.derive`.
5. Fechar geometria de combate, iniciativa, mapa de imagem e sincronizacao de
   dois acessos com permissao explicita. Coordenadas Z ficam preservadas; a
   restricao plana inicial nao e o contrato definitivo de terrenos/andares.
   Export numerico e caminhada plana ja entregues em L4. Nao usar
   `distance_presentation.py` (exclusivo de exibicao) como fonte de regra nem
   adivinhar modos/budget sobre prosa. Modos verticais, footprints grandes,
   modificadores dinamicos de movimento e dash continuam pendentes.
6. Somente entao ampliar matriz de tags e preparar publicacao privada via
   `/site-update`, com migration de schema, collectstatic, flag e rollback.

Nao reiniciar oficina/modelagem 3D, metas antigas, carreira ou Cisco como efeito
colateral. Nao liberar acesso publico. Nao usar ajuste manual de PV como prova de
que talentos, magias ou outras tags ja funcionam automaticamente.

## 7. Publicacao autorizada em 04/11/2026

Depois de revisar/commitar/pushar, deploy continua pelo `/site-update` monitorado.
A migration adiciona somente as tabelas do laboratorio e nao altera personagens.
Ativar `VTT_LAB_ENABLED=true` no ambiente desejado exige reinicio pelo fluxo
normal. Sem a flag, a rota responde 404. Rollback operacional: desligar a flag;
preservar os saves para diagnostico, sem desfazer migrations automaticamente.
O usuario autorizou commit/push e envio para producao. O deploy de codigo continua
pelo `/site-update` do BonfireBot, nao por um shell remoto. Push nao comprova
deploy. Manter a flag desligada ate o aceite privado; a primeira ficha real e o
teste concorrente em PostgreSQL continuam pendencias, nao evidencias inventadas.
As concessoes de subclasse precisam de conciliacao pela API instalada antes de
aplicar dados e publicar revisoes; isso nao acontece por executar a migration.

## 8. Caminhada L4: contrato e limites

`derive.movimento={schema:1,unit:'ft',speeds:{walk:30},warnings:[]}` e aditivo:
nao remove deslocamento textual nem altera a mecanica existente. A base legada
aceita somente valor inteiro/decimal com unidade `ft` ou `m`, ou ambos coerentes
com a conversao Bonfire 0,3 m/ft. Base desconhecida nao vira 30 ft por fallback.
O total soma apenas `velocidade_bonus` final, incluindo modificadores ja
resolvidos pelo motor. Nao foi criada migration de dados nem calculo por classe.
Metadados opcionais de voo/queda sao preservados, nao executados pela caminhada.

Mapa limitado a 64x64 no contrato (interface atual 24x18). Custo inteiro por
entrada na celula; padrao 12 unidades/celula, terreno dificil multiplicador 2.
Budget e floor(walk_ft * cost_scale / cell_feet), com aritmetica racional exata.
Parametros numericos pertencem aos dados do mapa. O caminho usa
[single_source_dijkstra oficial do NetworkX](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.single_source_dijkstra.html),
nao uma implementacao caseira; dependencia pinada [NetworkX 3.7](https://pypi.org/project/networkx/).
Aliados permitem passagem mas nao destino ocupado; inimigos e nao participantes
bloqueiam passagem. Condicao ativa ou velocidade ausente desabilita apenas a
caminhada, nao impede iniciar turno ou atacar. Nenhum obstaculo implica LoS.

Previa nao grava nem incrementa revisao. Confirmacao recalcula sob as mesmas
protecoes de transacao/revisao/recibo; recarregar nao recupera budget. Novo turno
do ator zera o gasto. Movimento manual nao permite contornar essa cobranca.
Fingerprints incluem helpers e versao NetworkX: saves anteriores nao sao
reinterpretados silenciosamente. Falta NetworkX: caminhada indisponivel, resto
do site nao depende de import eager da biblioteca.

Evidencias sao locais com fichas ficticias. O teste de export que depende do
banco real nao foi executado; suites puras/mock e adaptador HTTP isolado nao
equivalem a validar todas as fichas persistidas. Flag segue desligada; nenhuma
migration aplicada em PostgreSQL e nenhuma alteracao de producao nesta entrega.

## 9. Mapa L5

`state.presentation={background:null,grid_opacity:0.25}` e opcional para saves
anteriores. `background` recebe `url`, `cell_px`, `origin_x`, `origin_y`, `opacity`.
Comando `configure_presentation` usa a mesma revisao/CSRF/recibo dos demais;
recusado durante combate. Origem e tamanho aceitam fracao; proporcao da imagem e
preservada. Limpar imagem nao apaga terreno nem tokens.

Nao existe upload, proxy ou download pelo servidor. O navegador busca HTTPS ou
caminhos `/static/` e `/media/`, sem cookies, referrer ou redirecionamento.
PNG/JPG/WebP validados por assinatura e dimensoes antes do decode: ate 8 MiB,
16 milhoes de pixels e 8192 por lado; timeout de 15 segundos. Link externo
precisa permitir CORS. Cache de no maximo duas imagens por mesa; troca/fechamento
aborta pedidos e libera URLs/recursos. Erro aparece no painel, sem esconder os
tokens nem remover o mapa logico. Nao usar links com credenciais ou dados privados.

Arquivos: `home/vtt_lab_presentation.py`, teste de mesmo nome com prefixo `test_`,
`home/static/css/pages/vtt-lab-map.css`, form/JS do laboratorio e bridge visual
`bonfire-vtt/apps/client/src/siteLabRenderer.ts`. O build gera bundle e manifesto
de hashes; nao incluir o host/motor TS nem o WIP 3D no release do site.

Conferencia L5: 32 testes HTTP isolados, cinco de validacao pura da apresentacao
e 30 fluxos Playwright sem erros de pagina. Canvas com pixels diferentes apos
imagem, persistencia no reload, desktop/mobile sem overflow horizontal, remocao
e falha de URL cobertos. Capturas `docs/vtt/qa/map-desktop.png` e `map-mobile.png`.
API publicada: 20 testes dedicados isolados. Nenhuma dessas conferencias usou
PostgreSQL configurado ou credenciais de producao.
