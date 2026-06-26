# Verbos novos do sweep das 9 classes — 2026-06-17

> **STATUS: APROVADOS e DOBRADOS no `home/tag_library.json` + `dicionario-tags.md` (2026-06-17).**
> Este doc fica como histórico da decisão. As pendências de DADO (seção J) seguem abertas.

> As **tags de classe** das 9 classes já foram aplicadas (vocabulário existente).
> As **habilidades** estão rascunhadas (1 subagente por classe) mas dependem dos
> verbos abaixo. Regra do projeto: verbo genérico novo = **decisão do PO** antes de
> gravar. Decidir cada tema (aprova / ajusta / veta) e eu aplico todas as habilidades
> numa passada limpa.

## A. Conjuração — modos e seleção de magia
- **`slots:pact(resource:<slug>)`** — 4º modo de caster (pontos, recupera em descanso **curto**). Místico. *(ALTA — trava a classe inteira.)*
- **`cast{spell:pick{lista:<classe>, nivel<=N}}`** — conjurar magia **escolhida por filtro** (não slug fixo). Clérigo (Intervenção Divina), Mago, Místico (Arcana).
- **`always-prepared`** — magia sempre preparada, fora do limite. Paladino (Montaria), Místico, Mago.
- **`spell-level`** — variável = nível da magia conjurada. Feiticeiro (Dom da Criação).
- **`spell{active}` / `spell{lista:<classe>}`** — seletor da magia em conjuração / filtro por lista. Alvo do `modify:` da **Metamagia** (Feiticeiro).
- **`reset:level-up`** + filtro **`circulo<=N`** — retraining ao subir de nível; filtro por círculo. Místico, Mago.

## B. Testes de perícia
- **`check-bonus:<pericia>=<formula>`** — soma fixa a um teste nomeado. Clérigo (Ritos Sacros), Druida.
- **`check-swap:<a>=<b>(ability:<attr>)`** — troca a perícia/atributo de um teste. Clérigo (Voz do Cânone), Mago (Mente Afiada).
- **`expertise` por categoria** (ex.: todas as ferramentas). Artífice (Artesão Exímio).

## C. Sentidos / detecção / forçado
- **`sense:<tipo>(radius:ft)`** — sentido passivo da natureza de uma área. Clérigo.
- **`detect:{creature-type:[...], range:ft}`** — detectar criaturas/locais. Paladino (Sentido Divino).
- **`telepathy` / `share-senses`** — comunicação/percepção via vínculo. Místico.
- **`push:<ft>` / `pull:<ft>(from:<sel>)`** — **movimento forçado** de alvo (genérico, reaparece em várias classes). Místico.

## D. Eventos novos
- **`fail-check`** — par de `fail-save` (falha em teste de perícia). Guerreiro, Artífice.
- **`magic.deal-dmg`** — "sua magia causou dano". Clérigo.
- **`save-roll` / `ability-check` (gatilho)** — o **ato** de rolar teste (p/ reação de aliado). Artífice (Lampejo de Gênio).

## E. Ação / duração / limitadores
- **`grant:extra-action`** — ação completa extra (Surto de Ação). Guerreiro. *(ALTA — não cabe nos 4 custos nem em "execução".)*
- **`until-next-turn-end`** — duração até o fim do próximo turno. Guerreiro, Místico.
- **limitadores**: `1/spell` (Feiticeiro), `1/attack` (Guerreiro), `1/combat` (Mago), `1/long-rest{per:ciclo}` (Místico).
- **`target{same}`** — mesmo alvo do gatilho. Guerreiro (Ataque Estudado).

## F. Saves / no-*
- **`all-saves:+<formula>`** — bônus numérico em **todos** os saves. Paladino (Aura de Proteção), Artífice (Magnum Opus), Caçador (Instinto Afiado).
- **`auto-save-success`** — sucesso automático em save. Druida, Místico.
- completar família **`no-*`**: `no-los`, `no-somatic`, `no-verbal`, `no-sleep`, `no-crit-mult`.

## G. Recursos
- **`resource-restore` com quantidade/teto de nível** (hoje só `=all`). Paladino, Mago, Artífice, Clérigo.
- **`resource-cost:<rec>:1..all`** (faixa aberta). Druida.
- **`reset:2d4-long-rest`** (reset aleatório). Clérigo (Intervenção Divina Maior).
- **Pools a CRIAR na `TB_RecursoClasse`** (veto: pool não é tag):
  `canalizar-divindade` (Clérigo), `poco-de-cura` + `canalizar-divindade` (Paladino),
  usos grátis Arquimago/Maestria Arcana (Mago). Confirmar valores por nível.

## H. Itens mágicos / sintonização (Artífice — área inteira sem vocabulário)
- `sintonizacao` (teto) + `sintonizacao-ativa` (runtime), `raridade` (comum/incomum/raro),
  ferramentas como **foco** e categoria de proficiência (catálogo B6 só tem `ferreiro`/`instrumento-musical`).

## I. Diversos
- **`cleanse:magia`** (encerrar efeito de magia, não condição). Paladino (Toque Purificador).
- **`dmg:+X(pick:{tipo|...})`** — escolher tipo de dano inline. Druida.
- **`mark{}` de alvo único persistente** (não contador). Caçador (Marca do Caçador).
- **`ability:int|wis`** — atributo de conjuração **escolhível**. Caçador.

## J. Pendências de DADO (não-vocabulário)
- **Religar features de subclasse com `id_subclasse` nulo** (mesmo bug do Monge): **Mago** (Cronoturgia, Graviturgia, Fios do Destino, Ajuste de Densidade), e provavelmente outros.
- **Caçador:** habilidade "Conjuração" **duplicada** (Nv1 e Nv2, textos divergentes) — consolidar.
- **Feiticeiro:** habilidade base "Fonte de Magia" (conversão slot↔ponto) **não existe** na TB_ClasseHabilidade — criar.
- **Bardo:** "Palavras da Criação" usa slugs `palavra-de-poder-cura/matar` — confirmar em `TbMagia.slug`.
- **Normalização:** recurso de inspiração do Bardo é `dado-de-inspiracao`, mas tags antigas usam `dado-inspiracao` — alinhar.
