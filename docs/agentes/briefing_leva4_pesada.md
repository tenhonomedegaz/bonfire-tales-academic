# Briefing — parte PESADA da 4ª leva da staff (handoff para agente executor)

> Escrito em 2026-07-23 pelo agente de triagem. Autossuficiente: tudo que o executor
> precisa está aqui ou nos caminhos citados. O PO autorizou o trabalho; execute em
> ondas com verificação adversarial e commits atômicos, no padrão dos relatórios
> anteriores em `docs/agentes/`.

## Ambiente e regras do projeto (obrigatório ler antes)

- **Rodar Django (SEMPRE assim, via bash):**
  `cd "C:/Users/helio/Desktop/Projetos Bonfas/BonfireSite-main" && PYTHONIOENCODING=utf-8 POSTGRES_URL="" DB_ENGINE="" DJANGO_DEBUG="True" .venv/Scripts/python.exe manage.py <cmd>`
- **Espelho da prod** (personagem de teste Scar pk=11, Orc Bárbaro N11):
  mesma receita + `PYTHONPATH="<scratchpad>/diagnostico" DJANGO_SETTINGS_MODULE=scratch_settings`
  (lê `mirror.sqlite3`; se o scratchpad tiver sido limpo, reconstrua o espelho com
  `migrate` + `loaddata` do backup completo mais recente — ver §Backups).
- **Gates de qualidade por onda:** suíte completa (`manage.py test home`) 100% verde;
  `manage.py validate_tags` ERROR=0 WARN=0; invariantes do Scar no espelho:
  FOR 19 (+4), ataque desarmado +11 / dano `1d10 +8`, 15 m / 50 ft, PV 148,
  CA 19 com escudo comum (20 se trocado pro `+1 Escudo (*)`, 21 só em builds DES20/CON16).
- **Regras normativas:** descrição = fonte da verdade da mecânica; snake_case estrito
  (hífen só em slug de referência); regra da ficha-de-log (`always_active` = número
  estático; `while_active`/`toggle`/`trigger` = combate/VTT, NUNCA infla número);
  zero if-por-tipo (padrões genéricos/registry em `home/picks.py`); escrita de
  reprodução SEMPRE via TestCase (nunca `shell -c` com escrita — autocommit já vazou dados).
- **Commits:** português sem acentos, terminam com
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Um commit por onda coerente.
- **Deploy/conteúdo:** mudança de DADOS (tags/catálogo no `db.sqlite3` de dev) exige
  regenerar o restore consolidado ao final (método: gerador reconstruído de
  `home/deploy_sync.py`, CONTENT_MODELS sem mundo/mapa, memória nunca, json indent=2
  CRLF, sha256 dos bytes em disco; `.json`/`.report.json` SÓ NO DISCO em `ref/backups/`
  — gitignored, não commitar; só o relatório `.md` em `docs/agentes/` é versionado).
  Ver `docs/agentes/relatorio_restore_20260722_202656.md` como modelo.

## Itens (em ordem de prioridade)

### 1. Picks de USO aparecendo como escolha fixa (Máscara de Guerra, Aspecto Selvagem, Mordida Lacerante) — o mais importante

**Sintoma (PO):** as três aparecem como pendência/escolha no wizard e no level-up, mas são
escolhas **no momento do uso**: Máscara de Guerra se PREPARA num descanso longo gastando PO
(a descrição diz isso explicitamente — leia-a); Aspecto Selvagem escolhe-se ao conjurar;
Mordida Lacerante no ato do ataque com ação bônus. Não são estado permanente da ficha.
A Máscara "continua aparecendo no lvl up, não consigo trocar mas ainda está aqui".

**Causa-raiz conhecida:** a classificação de papéis do `pick:` (documentada em
`home/picks.py` — papéis A=wizard, B=referência, C=efeito) trata pick com contagem como
papel A (wizard) mesmo quando está DENTRO de `trigger=...`, `instant{...}` ou
`while_active{...}` — contexto de runtime. Ex.: tag da Máscara (TbTracoracial pk 2135):
`"trigger=long_rest, instant{ pick:mascara_guerra:1 }"` + `define{mascara_guerra: list{...}}`.

**Correção:** refinar a detecção do papel A: pick dentro de spans de
`trigger=`/`instant{}`/`while_active{}` = runtime (papel C), NUNCA vira grupo de
wizard/pendência (usar o mesmo mecanismo de span-stripping que `_strip_defines`/
`_strip_modify` já usam em `home/character_engine.py`). As três features somem do
wizard/level-up; escolhas já persistidas dessas features em `TbPersonagemEscolha`
devem ser ignoradas no readback (não deletar dados de personagem — só parar de ler).
A UI de USO (preparar a máscara no descanso etc.) é território do VTT futuro — NÃO construir.
Testes: as 3 features não geram pendência; picks legítimos (Metamagia, maestria,
Conhecimento Primitivo) continuam gerando.

### 2. Auditoria dos "equipáveis" — todos os itens mágicos viraram equipáveis (parse antigo)

**Sintoma (PO):** poção de cura tem botão "equipar"; Apito de Águia idem. "Num dos parses
anteriores isso foi feito sem querer... vai ser uma merda."

**Estado dos dados:** `TbItemMagico` tem colunas `slot`/`tipo` (autoritativas desde que os
metadados saíram das tags). A ponte com a fonte EN é `ref/Itens/itens_match.csv`
(954 linhas, tem tipo/categoria da fonte oficial).

**Correção (padrão análise→aplicação já usado no projeto):** derivar `equipavel` correto
por item: itens maravilhosos de uso (poções, pergaminhos, apitos, varinhas de carga?,
itens "usar e pronto") não são equipáveis; armas/armaduras/escudos/anéis/mantos/botas/
elmos/cintos/manoplas etc. são. Fan-out de análise read-only por lotes propondo
`equipavel`/slot corrigido com confiança (fonte EN + tipo + descrição), aplicação serial
com log (`{tabela, pk, campo, antes, depois}`), holds de baixa confiança para o PO.
Cuidado: personagens em prod já têm itens equipados — item que virar não-equipável deve
ser desequipado GRACIOSAMENTE no derive (ignorar equipado=True de item não-equipável,
sem deletar linha). Isso é MUDANÇA DE DADOS → restore novo ao final.

### 3. Consumível ≠ recurso recuperável (poções com "usos" que voltam no descanso)

**Sintoma (PO):** 3 poções = recurso com 3 usos que RECUPERA no descanso. Certo: qtd do
item consumível; usar = consumir 1 (qtd-1, deletando a linha em 0); NUNCA recupera.
**Onde olhar:** como consumíveis entram no painel de recursos da ficha
(`home/views.py` — busca por recursos/consumíveis; o empilhamento por `qtd` em
`TbPersonagemItem` já existe). Separar: recursos de classe (recuperam por descanso)
vs consumíveis (decrementam qtd). O botão "Usar" de consumível consome do inventário.
Depende conceitualmente do item 2 (o que é consumível) — fazer junto ou logo depois.

### 4. Fetch-ificar o resto do editar-ficha (página recarrega a cada alteração)

**Sintoma (PO):** qualquer alteração recarrega a página — "horrível pra adicionar
missões manualmente" (staff registra aventuras uma a uma).
**Estado:** compra/venda já é fetch (loja_ficha.js); level-up saiu pra página própria.
Restam PRG: staffbox (registrar aventuras, conceder item, reverter), equipar/desequipar/
sintonizar, usar recurso, editar info. **Correção:** mesmo padrão do loja_ficha.js —
resposta JSON quando XHR (mantendo redirect pra POST clássico), atualização parcial
do DOM. Priorizar o staffbox de aventuras (dor imediata da staff).

### 5. Subir de nível encadeado

**Sintoma:** com várias aventuras acumuladas, o wizard sobe 1 nível e volta pra ficha.
**Correção:** ao confirmar, se ainda houver nível disponível pelo teto, oferecer
"Continuar para o nível N+1" reabrindo o wizard já no próximo nível (loop), sem
redesign — `home/templates/home/pages/subir_nivel.html` + `subir_nivel.js` +
`personagem_levelup_aplicar` (a resposta já traz pendências/status).

### 6. Trocar maestria no descanso longo não funciona

**Sintoma (PO):** "Maestria não tá dando pra trocar (sendo que dá pra trocar no
descanso longo)". Existe `trocar_maestria.html` — investigar se a mudança do par-único
(arma pode repetir; par arma+maestria não) quebrou o fluxo de troca, ou se a entrada
sumiu da ficha. Regra: troca no descanso longo. Corrigir o fluxo existente.

### 7. UX do painel de escolhas (wizard/level-up)

- Mostrar a **descrição completa** da opção selecionada (não só o nome tipo "A Magia") —
  os `define{list}` têm os dados; TbOpcaojogo tem descrição; renderizar no card.
- Eliminar o clique "Escolher" por opção — seleção direta no controle já enfileira
  (padrão do resto do wizard).

### 8. Housekeeping do próximo deploy

- Rollback novo = `backup_completo_20260722_230533` (backup completo → TEM personagens).
  Citar no próximo relatório de restore no lugar do de 18/07.
- Itens fungal (glowing fungal clothes / warm fungal cloak): aguardando fonte da staff.
- Axe Beak: criatura/montaria pro bestiário — aguardando decisão do PO.
- Repaginada da raça Vampiro + Bestial/Folken: rework aguardando o PO.

## O que NÃO fazer

- Não mexer no mundo/mapa/organizações (prod vence; fora do restore por ausência).
- Não tocar `equipamento` de TbClasse além do já feito; não versionar restores.
- Não construir UI de VTT (toggles/preparação em combate) — só tirar do wizard o que
  não pertence a ele (item 1).
- Não commitar `db.sqlite3`, `ref/`, `scratch/`.

## Já corrigido na onda leve (não redescobrir)

CA com escudo MÁGICO no cálculo (itens mágicos entram; escudos não empilham);
bloqueio universal de perícia (qualquer fonte trava toda lista — server+client+universes);
CSS dos botões de descanso; descrição das magias na aba de magias.
(Ver commit da onda "leva 4 leve" no git log.)
