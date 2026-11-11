# Candidatos a REMOÇÃO de tags — DECISÕES DO PO APLICADAS

> **STATUS: APLICADO (2026-07-07).** As decisões do PO foram executadas no banco local
> (SQLite dev, fonte do conteúdo de prod). Backup pré-remoções em
> `scratchpad/audtags/backup_pre_remocoes.sqlite3`; antes/depois de cada registro em
> `scratchpad/audtags/aplicado_remocoes.json`. `validate_tags` pós-edição: **ERROR=25**
> (idêntico ao baseline pré-existente Virtudes/Paladino — **zero erro novo**), WARN=2
> (ambos pré-existentes, nenhum introduzido). Cada item abaixo traz `→ DECISÃO:`.
>
> **NADA AQUI FOI REMOVIDO.** Este arquivo lista as tags que a auditoria semântica
> identificou como **candidatas a remoção** (`rp_only` e `tag_sobrando` **confirmados**),
> mas que **exigem sua decisão** antes de qualquer alteração no banco. Diferente das
> correções aplicadas (ver [`auditoria_tags_semantica.md`](auditoria_tags_semantica.md)),
> remoção destrói informação — por isso é decisão do PO, não da auditoria.
>
> **Total: 26 candidatos** — 12 `rp_only` + 14 `tag_sobrando`.
>
> **Duas categorias, duas naturezas:**
> - **`rp_only`** — a tag replica fielmente a descrição, mas a **condição não é
>   avaliável pelo motor** a partir do estado da ficha (contexto narrativo: bioma,
>   material, clima, tema da rolagem). Padrão calibrado pelo PO: anão com vantagem em
>   Percepção `context:pedra`. Recomendação padrão: **remover** o gate/tag, OU **manter
>   como RP marcado** (deixar explícito que é resolvido pelo mestre, fora do motor). A
>   parte **incondicional** de cada traço (quando existe) permanece intacta.
> - **`tag_sobrando`** — a tag **não tem base na descrição** (não há mecânica descrita
>   que a justifique). Recomendação padrão: **remover**.
>
> **Legenda:** `[ ]` = pendente de decisão. Marque `[x]` ao decidir. Ação sugerida entre
> **remover** e **manter como RP marcado**.

---

## A) `rp_only` — contexto não-programável (12)

### TB_ClasseHabilidade
- [x] **id 1057 — Passos Invisíveis** — tag: `while_active{action:bonus_action, instant{hide}}`
  (o problema é a parte "Rastros Apagados" da descrição, **sem tag** — o que a auditoria
  aponta é que ela **não deve ganhar tag**). Evidência: "Rastros Apagados: você não pode
  ser rastreado por meios não mágicos; rastreadores/animais falham automaticamente."
  Não há catálogo/perícia de "rastreamento" no motor. **Recomendação: manter sem tag (RP).**
  → DECISÃO: NENHUMA mudança no banco. "Rastros Apagados" permanece sem tag (RP, a critério do mestre). Só marcado aqui.

### TB_TracoRacial
- [x] **id 2020 — Senso da Pedra** — remover o qualificador `(context:pedra)` de
  `adv:check{percepcao}(context:pedra)` e `adv:check{investigacao}(context:pedra)`.
  Evidência: "relacionado a passagens secretas, desmoronamentos ou obras de engenharia em
  pedra" — narrativo. A condição de toque já está em `requires:touching{pedra}` (programável)
  e **permanece**. **Recomendação: remover só o `context:pedra`, mantendo
  `requires:touching{pedra}` + `adv:check{...}`.**
  → DECISÃO: aplicado. Removidos os dois `(context:pedra)`. Resultado: `always_active{ requires:touching{pedra}, adv:check{percepcao}, adv:check{investigacao} }`. `requires:touching{pedra}` preservado. Validação limpa.
- [x] **id 2074 — Passo da Seiva** — tag `while_active{requires:terreno_natural, speed:+5ft}`.
  Evidência: "enquanto estiver em terreno natural, como floresta, pântano ou selva".
  `terreno_natural` não é catálogo/estado da ficha. O bônus de 1d4 em Sobrevivência/Natureza
  (incondicional) está fora do `while_active` e **permanece**. **Recomendação: remover o gate.**
  → DECISÃO: aplicado (TOGGLE). Removido `requires:terreno_natural`; resta `while_active{ speed:+5ft }` (toggleável na ficha, a critério do mestre). O 1d4 em Sobrevivência/Natureza intacto. Validação limpa.
- [x] **id 2060 — Passo Entre Raízes** — tag `hide{while:lightly_obscured(from:folhagem | chuva_forte | neve | nevoa | fenomeno_natural)}`.
  Evidência: fenômenos climáticos/ambientais não registráveis. **Recomendação: remover/RP.**
  → DECISÃO: aplicado (TOGGLE, reescrita). O efeito de esconder virou habilidade toggleável no padrão canônico do banco (`while_active{action:bonus_action, instant{hide}}`, mesmo padrão de id 1057 e 897), **sem** a condição narrativa de clima/folhagem. As outras duas cláusulas (`speed:+5ft`, `no_difficult_terrain{from:vegetacao_nao_magica}`) permanecem. Validação limpa.
- [x] **id 2101 — Raízes Sem Correntes** — tag `while_active{requires:terreno_natural, speed:+10ft, cond_immune:agarrado, cond_immune:restringido}`.
  Evidência: bioma ambiental como gate. **Recomendação: remover o `requires:terreno_natural`
  (avaliar com o PO se o efeito vira sempre-ativo ou fica a critério do mestre).**
  → DECISÃO: aplicado (TOGGLE). Removido `requires:terreno_natural`; resta `while_active{ speed:+10ft, cond_immune:agarrado, cond_immune:restringido }` (toggleável na ficha, a critério do mestre). Validação limpa.
- [x] **id 2119 — Camuflagem Natural** — tag `always_active{adv:check{furtividade}, requires:terreno{floresta | selva | pantano}}`.
  Evidência: bioma. **Recomendação: remover o `requires:terreno{...}`.**
  → DECISÃO: toggle (revisado pelo PO). Removido `requires:terreno{floresta|selva|pantano}` e o bloco convertido de `always_active` para `while_active`; resta `while_active{ adv:check{furtividade} }` (toggleável na ficha, a critério do mestre, consistente com 2060/2074/2101). Validação limpa.
- [x] **id 2131 — Caminhante da Neve** — remover só o `adv:check{acrobacia}(for:equilibrio_em_{gelo | neve | escorregadio})`.
  Evidência: superfície do ambiente. A parte `no_difficult_terrain(source:{gelo|neve|escorregadio})`
  é mecânica de mapa **e permanece**. **Recomendação: remover só a vantagem de Acrobacia contextual.**
  → DECISÃO: aplicado (CIRÚRGICO). Removido só `adv:check{acrobacia}(for:equilibrio_em_{...})`; resta `always_active{ no_difficult_terrain(source:{gelo | neve | escorregadio}) }`. Validação limpa.
- [x] **id 2136 — Oratória Tribalística** — tag `always_active{adv:check{historia}, requires:tema{tribos | batalhas_antigas | bestas_lendarias}}`.
  Evidência: assunto narrativo da rolagem. **Recomendação: remover o gate.**
  → DECISÃO: toggle (revisado pelo PO). Removido `requires:tema{...}` e o bloco convertido de `always_active` para `while_active`; resta `while_active{ adv:check{historia} }` (toggleável na ficha, a critério do mestre, consistente com 2119); `prof:sobrevivencia` e `prof:historia` intactos. Validação limpa.
- [x] **id 2242 — Regeneração Sanguínea** — remover só o ramo `contact{agua_benta}` de
  `restriction{since_last_turn: take_damage{radiante} or contact{agua_benta}}`. A parte
  `take_damage{radiante}` é programável **e permanece**. **Recomendação: remover só `contact{agua_benta}`.**
  → DECISÃO: aplicado (REESCRITA — PO: "água benta é item REAL"). O ramo `contact{agua_benta}` (string livre) virou `contact{item:holy-water}`, referenciando o item real **Água Benta** (`TB_ItemMundano`, slug `holy-water`, id 161). Forma programável: `restriction{since_last_turn: take_damage{radiante} or contact{item:holy-water}}`. `take_damage{radiante}` intacto. Validação limpa.
- [x] **id 2243 — Presença da Noite** — remover os blocos `context{rastros, emboscadas}` e
  `context{sinal_fisico or cheiro}`. `target{sangrando}` e `in_dim_light` são programáveis
  **e permanecem**. **Recomendação: remover só os `context{...}`.**
  → DECISÃO: aplicado (CIRÚRGICO). Removidos `context{rastros, emboscadas}` e `requires:context{sinal_fisico or cheiro}`; resta `adv:check{percepcao}(requires:target{sangrando}, in_dim_light)`. `always_active` e `prof:percepcao` intactos. Validação limpa.
- [x] **id 2244 — Pressão Solar** — remover `unless:in:cobertura{cavernas, edificios} or context{nevoa_velmourn}`.
  Evidência: `cobertura` é enum de cobertura em combate (half/three_quarters/total), não
  "estar dentro de estrutura". **Recomendação: remover/RP.**
  → DECISÃO: aplicado (CIRÚRGICO). Removida a cláusula inteira `unless:in:cobertura{cavernas, edificios} or context{nevoa_velmourn}`. Restam `always_active`, os dois `while:in_sunlight{...}` (penalidades e supressão de regeneração). Validação limpa.
- [x] **id 2248 — Educação Vesánia** — remover `(context:emocoes_alheias)` de `adv:check{intuicao}`.
  Evidência: intenção declarada do teste. **Recomendação: remover só o `context`.**
  → DECISÃO: aplicado (REESCRITA — PO: "tirar tudo, habilidade descritiva; jogador pergunta pro mestre"). `TagsJSON` **zerado** (lista vazia `[]`), preservando a descrição PT. Nota: decisão do PO foi além da recomendação (remoção total, não só o `context`). Validação limpa (sem tags = sem diagnósticos).

---

## B) `tag_sobrando` — sem base na descrição (14)

### TB_ClasseHabilidade
- [x] **id 809 — Maestria em Armas** — tag `swap:long_rest` **duplicada** (aparece 2×).
  Descrição menciona a troca em descanso longo uma única vez. **Recomendação: remover a 2ª ocorrência.**
  → DECISÃO: aplicado. Removida a 2ª `swap:long_rest`. Resultado: `["pick:arma:2", "swap:long_rest"]`. Validação limpa.
- [x] **id 1517 — Bushidō** — tag `swap:long_rest`. A descrição (escolha das Armas de
  Kensei) não menciona troca em descanso longo. **Recomendação: remover.**
  → DECISÃO: aplicado. Removido `swap:long_rest`. Demais 7 tags (proficiências, `pick:arma`, `add_mastery:wielded`, etc.) intactas. Validação limpa.
- [x] **id 1545 — Um com a Lâmina** — tag `action=bonus_action`. Descrição: "no início do
  seu turno, você pode gastar 1 ponto de Ki para entrar em foco" — sem custo de Ação Bônus.
  **Recomendação: remover.** (Confiança baixa — o autor marcou "reportar apenas".)
  → DECISÃO: aplicado. Removido `action=bonus_action`. Restam `trigger=turn_start`, `resource_cost:pontos_de_ki:1`, `duration:10`, o `while_active{...}`. Validação limpa.

### TB_ItemMundano — DECISÃO DO PO INVERTIDA: as tags estão CORRETAS; sincroniza-se a DESCRIÇÃO
> PO: "as tags estão CORRETAS; a descrição veio de outra fonte sem as maestrias — quem muda é
> a descrição". Portanto, para cada arma abaixo **as tags ficam intactas** e a **propriedade é
> acrescentada à descrição** (na linha `**Propriedades:**` e como bullet em `#### Regras rápidas`),
> no mesmo estilo do texto existente. Não é remoção.
- [x] **id 1 — Adaga** — `add_property:adaptavel(cortante)`.
  → DECISÃO: descrição sincronizada. Adicionado "Adaptável (cortante)" à linha de Propriedades + bullet em Regras rápidas. Tag intacta.
- [x] **id 3 — Bordão** — `add_property:empunhadura_longa`.
  → DECISÃO: descrição sincronizada. Adicionado "Empunhadura Longa" à linha de Propriedades + bullet. Tag intacta.
- [x] **id 7 — Lança** — `add_property:empunhadura_longa`.
  → DECISÃO: descrição sincronizada. Adicionado "Empunhadura Longa" à linha de Propriedades + bullet. Tag intacta.
- [x] **id 17 — Alabarda** — `add_property:empunhadura_longa`.
  → DECISÃO: descrição sincronizada. Adicionado "Empunhadura Longa" à linha de Propriedades + bullet. Tag intacta.
- [x] **id 21 — Cimitarra** — `add_property:tecnica(1d8)`.
  → DECISÃO: descrição sincronizada. Adicionado "Técnica (1d8)" à linha de Propriedades + bullet (fraseado copiado do padrão Katana/Nunchaku, que já listam Técnica (1d8)). Tag intacta.
- [x] **id 22 — Espada Curta** — `add_property:adaptavel(cortante)`.
  → DECISÃO: descrição sincronizada. Adicionado "Adaptável (cortante)" à linha de Propriedades + bullet. Tag intacta.
- [x] **id 24 — Espada Longa** — `add_property:adaptavel(perfurante)`.
  → DECISÃO: descrição sincronizada. Adicionado "Adaptável (perfurante)" à linha de Propriedades + bullet. Tag intacta.
- [x] **id 26 — Glaive** — `add_property:empunhadura_longa`.
  → DECISÃO: descrição sincronizada. Adicionado "Empunhadura Longa" à linha de Propriedades + bullet (fraseado copiado do padrão Martelo Haste, que já lista Empunhadura Longa). Tag intacta.

### TB_TracoRacial
- [x] **id 2308 — Alento Primordial** — tag `requires:!has:ability{segundo_alento}`.
  A descrição não menciona restrição por já possuir "Segundo Alento"; o gate bloqueia o
  traço inteiro sem base textual. **Recomendação: remover o `requires`.**
  → DECISÃO: aplicado (REESCRITA DE PRÉ-REQUISITO — PO: "é pré-requisito; já existe tag de restriction"). Trocado `requires:!has:ability{segundo_alento}` por `restriction{ability{segundo_alento}}` — forma canônica de gate da lib (mesmo padrão de `restriction{equiped{armor}}`), programável e sem dupla negação. A referência `ability{segundo_alento}` resolve no banco (sem #REF!). Validação limpa (o `has:` verb, que geraria WARN, foi eliminado). Semântica preservada: bloqueia selecionar/usar o traço se já possui Segundo Alento.

### TB_OpcaoJogo
- [x] **id 80 — Égide Aparadora** — tag `equiped{escudo}`. A descrição (Reação + 2 pontos
  de Convicção para somar CHA à CA de uma criatura) **não menciona escudo**. **Recomendação: remover.**
  → DECISÃO: aplicado. Removido `equiped{escudo}` de dentro do `instant{...}`. As demais cláusulas ficam. OBS: o ERROR de `conviccao` (`resource_cost:conviccao`) é **baseline pré-existente Virtudes/Paladino** (decisão em aberto do PO) — NÃO tocado; segue igual pré e pós.
- [x] **id 99 — Reforço de Aura** — tag `1/short_rest`. A descrição só impõe o custo de 4
  pontos de Convicção + Ação Bônus, sem limite por descanso. **Recomendação: remover.**
  → DECISÃO: aplicado. Removido `1/short_rest` da 1ª cláusula (resta `action=bonus_action, resource_cost:conviccao:4`). OBS: o ERROR de `conviccao` é **baseline pré-existente Virtudes/Paladino** — NÃO tocado.

---

## Como procedeu (histórico — CONCLUÍDO 2026-07-07)

1. Backup pré-remoções: `scratchpad/audtags/backup_pre_remocoes.sqlite3`.
2. Para cada item: leitura do registro atual → edição mínima → validação da tag resultante.
3. `validate_tags` completo pós-edição: **ERROR=25 / WARN=2 / INFO=0**, idêntico ao baseline
   (todos os 25 ERROR são o pré-existente `conviccao`/`golpe_da_conviccao` de Virtudes/Paladino,
   decisão em aberto do PO — **zero erro novo, zero warn novo**).
4. Antes/depois de cada registro tocado: `scratchpad/audtags/aplicado_remocoes.json`
   (17 edições de tag + 8 de descrição de arma = 25 registros).

### Notas para o PO (decisões que ficaram sempre-ativas — candidatas a virar toggle depois)
- **2119 Camuflagem Natural** e **2136 Oratória Tribalística**: revisado pelo PO em 07/07 —
  convertidos de `always_active` para `while_active` (toggle na ficha, a critério do mestre),
  consistente com 2060/2074/2101. Ver decisões atualizadas acima.
- **2242 Regeneração Sanguínea**: o ramo de água benta agora referencia o item real
  (`item:holy-water`, `TB_ItemMundano` id 161). Não há checagem de #REF! para itens no motor
  hoje; se um índice de itens for adicionado ao `DataIndex`, essa referência passará a ser validada.
