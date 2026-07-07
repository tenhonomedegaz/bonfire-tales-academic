# Candidatos a REMOÇÃO de tags — aguardando confirmação do PO

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
- [ ] **id 1057 — Passos Invisíveis** — tag: `while_active{action:bonus_action, instant{hide}}`
  (o problema é a parte "Rastros Apagados" da descrição, **sem tag** — o que a auditoria
  aponta é que ela **não deve ganhar tag**). Evidência: "Rastros Apagados: você não pode
  ser rastreado por meios não mágicos; rastreadores/animais falham automaticamente."
  Não há catálogo/perícia de "rastreamento" no motor. **Recomendação: manter sem tag (RP).**

### TB_TracoRacial
- [ ] **id 2020 — Senso da Pedra** — remover o qualificador `(context:pedra)` de
  `adv:check{percepcao}(context:pedra)` e `adv:check{investigacao}(context:pedra)`.
  Evidência: "relacionado a passagens secretas, desmoronamentos ou obras de engenharia em
  pedra" — narrativo. A condição de toque já está em `requires:touching{pedra}` (programável)
  e **permanece**. **Recomendação: remover só o `context:pedra`, mantendo
  `requires:touching{pedra}` + `adv:check{...}`.**
- [ ] **id 2074 — Passo da Seiva** — tag `while_active{requires:terreno_natural, speed:+5ft}`.
  Evidência: "enquanto estiver em terreno natural, como floresta, pântano ou selva".
  `terreno_natural` não é catálogo/estado da ficha. O bônus de 1d4 em Sobrevivência/Natureza
  (incondicional) está fora do `while_active` e **permanece**. **Recomendação: remover o gate.**
- [ ] **id 2060 — Passo Entre Raízes** — tag `hide{while:lightly_obscured(from:folhagem | chuva_forte | neve | nevoa | fenomeno_natural)}`.
  Evidência: fenômenos climáticos/ambientais não registráveis. **Recomendação: remover/RP.**
- [ ] **id 2101 — Raízes Sem Correntes** — tag `while_active{requires:terreno_natural, speed:+10ft, cond_immune:agarrado, cond_immune:restringido}`.
  Evidência: bioma ambiental como gate. **Recomendação: remover o `requires:terreno_natural`
  (avaliar com o PO se o efeito vira sempre-ativo ou fica a critério do mestre).**
- [ ] **id 2119 — Camuflagem Natural** — tag `always_active{adv:check{furtividade}, requires:terreno{floresta | selva | pantano}}`.
  Evidência: bioma. **Recomendação: remover o `requires:terreno{...}`.**
- [ ] **id 2131 — Caminhante da Neve** — remover só o `adv:check{acrobacia}(for:equilibrio_em_{gelo | neve | escorregadio})`.
  Evidência: superfície do ambiente. A parte `no_difficult_terrain(source:{gelo|neve|escorregadio})`
  é mecânica de mapa **e permanece**. **Recomendação: remover só a vantagem de Acrobacia contextual.**
- [ ] **id 2136 — Oratória Tribalística** — tag `always_active{adv:check{historia}, requires:tema{tribos | batalhas_antigas | bestas_lendarias}}`.
  Evidência: assunto narrativo da rolagem. **Recomendação: remover o gate.**
- [ ] **id 2242 — Regeneração Sanguínea** — remover só o ramo `contact{agua_benta}` de
  `restriction{since_last_turn: take_damage{radiante} or contact{agua_benta}}`. A parte
  `take_damage{radiante}` é programável **e permanece**. **Recomendação: remover só `contact{agua_benta}`.**
- [ ] **id 2243 — Presença da Noite** — remover os blocos `context{rastros, emboscadas}` e
  `context{sinal_fisico or cheiro}`. `target{sangrando}` e `in_dim_light` são programáveis
  **e permanecem**. **Recomendação: remover só os `context{...}`.**
- [ ] **id 2244 — Pressão Solar** — remover `unless:in:cobertura{cavernas, edificios} or context{nevoa_velmourn}`.
  Evidência: `cobertura` é enum de cobertura em combate (half/three_quarters/total), não
  "estar dentro de estrutura". **Recomendação: remover/RP.**
- [ ] **id 2248 — Educação Vesánia** — remover `(context:emocoes_alheias)` de `adv:check{intuicao}`.
  Evidência: intenção declarada do teste. **Recomendação: remover só o `context`.**

---

## B) `tag_sobrando` — sem base na descrição (14)

### TB_ClasseHabilidade
- [ ] **id 809 — Maestria em Armas** — tag `swap:long_rest` **duplicada** (aparece 2×).
  Descrição menciona a troca em descanso longo uma única vez. **Recomendação: remover a 2ª ocorrência.**
- [ ] **id 1517 — Bushidō** — tag `swap:long_rest`. A descrição (escolha das Armas de
  Kensei) não menciona troca em descanso longo. **Recomendação: remover.**
- [ ] **id 1545 — Um com a Lâmina** — tag `action=bonus_action`. Descrição: "no início do
  seu turno, você pode gastar 1 ponto de Ki para entrar em foco" — sem custo de Ação Bônus.
  **Recomendação: remover.** (Confiança baixa — o autor marcou "reportar apenas".)

### TB_ItemMundano (propriedade de arma sem base na descrição)
- [ ] **id 1 — Adaga** — `add_property:adaptavel(cortante)`. Descrição: só Acuidade, Leve,
  Arremesso. **Recomendação: remover.**
- [ ] **id 3 — Bordão** — `add_property:empunhadura_longa`. Descrição: só Versátil (1d8).
  **Recomendação: remover.**
- [ ] **id 7 — Lança** — `add_property:empunhadura_longa`. Descrição: só Arremesso, Versátil.
  **Recomendação: remover.**
- [ ] **id 17 — Alabarda** — `add_property:empunhadura_longa`. Descrição: Pesada, Alcance,
  Two-Handed. **Recomendação: remover.**
- [ ] **id 21 — Cimitarra** — `add_property:tecnica(1d8)`. Descrição: Acuidade, Leve.
  **Recomendação: remover.**
- [ ] **id 22 — Espada Curta** — `add_property:adaptavel(cortante)`. Descrição: Acuidade, Leve.
  **Recomendação: remover.**
- [ ] **id 24 — Espada Longa** — `add_property:adaptavel(perfurante)`. Descrição: Versátil (1d10).
  **Recomendação: remover.**
- [ ] **id 26 — Glaive** — `add_property:empunhadura_longa`. Descrição: Pesada, Alcance,
  Two-Handed. **Recomendação: remover.**

### TB_TracoRacial
- [ ] **id 2308 — Alento Primordial** — tag `requires:!has:ability{segundo_alento}`.
  A descrição não menciona restrição por já possuir "Segundo Alento"; o gate bloqueia o
  traço inteiro sem base textual. **Recomendação: remover o `requires`.**

### TB_OpcaoJogo
- [ ] **id 80 — Égide Aparadora** — tag `equiped{escudo}`. A descrição (Reação + 2 pontos
  de Convicção para somar CHA à CA de uma criatura) **não menciona escudo**. **Recomendação: remover.**
- [ ] **id 99 — Reforço de Aura** — tag `1/short_rest`. A descrição só impõe o custo de 4
  pontos de Convicção + Ação Bônus, sem limite por descanso. **Recomendação: remover.**

---

## Como proceder

1. Marque cada item como **remover** ou **manter como RP marcado**.
2. Para `rp_only`, a remoção incide **apenas** sobre o qualificador/gate narrativo; a parte
   incondicional ou programável de cada traço (destacada acima) **não deve ser tocada**.
3. Após sua decisão, uma passada de aplicação (com backup + `validate_tags` de
   não-regressão) executa as remoções aprovadas — nunca antes.
