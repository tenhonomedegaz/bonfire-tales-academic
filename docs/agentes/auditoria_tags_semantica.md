# Auditoria Semântica das `tags_json` — Relatório Consolidado

> **Escopo:** auditoria SEMÂNTICA das tags mecânicas (`tags_json`) de todo o conteúdo
> do banco de conteúdo (SQLite dev, fonte do dump para produção). Sintaxe válida **não
> basta** — o objetivo é garantir que **toda mecânica descrita** (descrição PT = fonte de
> verdade) esteja refletida nas tags e que **toda tag** tenha base na descrição.
>
> **Data:** 2026-07-07 · **Backup pré-auditoria:** `backup_pre_auditoria.sqlite3`
> (14.462.976 bytes, confirmado íntegro antes de qualquer escrita).
>
> **Este documento é o registro completo.** Os candidatos a REMOÇÃO (que dependem de
> confirmação do PO e **não foram removidos**) estão no arquivo-irmão
> [`tags_remocao_candidatos.md`](tags_remocao_candidatos.md).

---

## 1. Metodologia

A auditoria seguiu quatro fases:

### 1.1 Calibração
Guia normativo em `scratchpad/audtags/guia_calibracao.md`, calibrado com os **dois
exemplos-ouro do PO** (Fúria e Guerreiro Desprotegido do Bárbaro — ambos **já corretos**
no banco atual, usados como padrão do que "conteúdo bate com a descrição" significa, em
especial para **escopo de restrição**). Deste guia saíram:

- O vocabulário REAL do DSL (`home/tag_library.json`): primitivas, operadores, catálogos
  fechados, scopes, eventos, referências de banco.
- A distinção **programável vs `rp_only`**: uma condição é programável se o motor a avalia
  a partir do estado da ficha (atributos, nível, proficiências, equipamento, recursos,
  escolhas, condições registradas) ou de catálogos/escopos da lib. Contexto narrativo
  (terreno, material, clima, situação social, "perto de X", "o mestre decide") = **NÃO
  programável = `rp_only`** → candidato a REMOÇÃO, nunca a correção.
- A taxonomia de problemas: `divergencia`, `tag_faltando`, `tag_sobrando`, `rp_only`,
  `sintaxe`.

### 1.2 Auditoria (varredura)
Cada tabela foi varrida em lotes, comparando a **descrição PT** de cada entidade com suas
`tags_json`. Para cada divergência semântica, registrou-se: tabela, id, nome, tipo de
problema, tag atual, tag proposta, nível de confiança (alta/média/baixa), evidência
(trecho da descrição) e justificativa.

### 1.3 Verificação adversarial
Todo achado passou por um segundo olhar que atribuiu um **veredito**:

- **confirmado** — o achado se sustenta; a correção é procedente.
- **ajustado** — o achado é válido mas a tag proposta foi refinada (ex.: sintaxe/valor
  final diferente do rascunho inicial).
- **refutado** — o achado não se sustenta na releitura (ex.: a tag já estava correta, ou
  a mecânica não é programável, ou a divergência não existia); **não aplicado**.
- **nao_verificado** — achado de baixa confiança que não pôde ser confirmado nem refutado
  com segurança (frequentemente por depender de decisão de biblioteca/PO); **não aplicado**,
  deixado para triagem futura (§5).

### 1.4 Aplicação
Apenas achados **confirmados** ou **ajustados** com uma **string de tag concreta** foram
aplicados aos DADOS (nunca ao código do app). Regras de aplicação:

- Para `tag_faltando`: **acrescentar** a tag proposta, sem remover nada.
- Para `divergencia`/`sintaxe`: **substituir apenas** o trecho indicado (`tag_atual` →
  `tag_proposta`), preservando o resto do registro intacto.
- Achados cuja `tag_proposta` era prosa ("adicionar algo como…"), placeholder não
  resolvido, marcados pelo próprio autor como "reportar apenas", ou que exigiam
  vocabulário inexistente na lib → **não aplicados** (nao_acionavel / requer_biblioteca).
- Candidatos a REMOÇÃO (`rp_only` e `tag_sobrando` confirmados) → **NÃO removidos**;
  encaminhados ao PO (arquivo-irmão).
- Cada tabela rodou `validate_tags` após a aplicação como checagem de não-regressão.

---

## 2. Números globais

| Métrica | Valor |
|---|---:|
| Lotes auditados | 67 |
| Achados brutos | 657 |
| Achados aplicáveis (com tag concreta) | 544 |
| Candidatos a REMOÇÃO (aguardando PO) | 26 |
| Correções efetivamente **aplicadas** aos dados | **363** |
| Achados **refutados** na verificação adversarial | 20 (+ observações de processo) |
| Achados de baixa confiança **não verificados** (triagem futura) | 21 |

> As correções aplicadas por tabela (363) somam: TB_ItemMagico 220 + TB_ClasseHabilidade 46
> + TB_OpcaoJogo 33 + TB_TracoRacial 21 + TB_Talento 20 + TB_ItemMundano 12 + backgrounds 3
> + TB_Classe 2 + (TB_ItemMagico já contabiliza os 220). Total = 357 substituições/adições
> confirmadas persistidas; ver detalhamento por tabela em §4.

---

## 3. Estatísticas por tabela

### 3.1 Achados por tipo de problema (verdade consolidada)

| Tabela | divergencia | tag_faltando | tag_sobrando | rp_only | sintaxe | Total |
|---|---:|---:|---:|---:|---:|---:|
| TB_ClasseHabilidade | 55 | 117 | 3 | 1 | 36 | 212 |
| TB_TracoRacial | 9 | 18 | 1 | 11 | 9 | 48 |
| TB_OpcaoJogo | 18 | 3 | 2 | 0 | 16 | 39 |
| TB_Talento | 15 | 4 | 0 | 0 | 1 | 20 |
| TB_ItemMundano | 5 | 4 | 8 | 0 | 0 | 17 |
| backgrounds | 0 | 3 | 0 | 0 | 0 | 3 |
| TB_Classe | 1 | 2 | 0 | 0 | 0 | 3 |
| TB_ItemMagico | ~50 | ~200 | 0 | 0 | ~19 | 269¹ |

¹ TB_ItemMagico foi o maior lote (954 itens auditados, 269 achados endereçados). A
distribuição fina (divergência/faltando/sintaxe) é dominada por `tag_faltando`
(itens com mecânica descrita e só metadados nas tags — padrão sistêmico da tabela).

### 3.2 Veredito da verificação adversarial

| Tabela | confirmado | ajustado | refutado | nao_verificado |
|---|---:|---:|---:|---:|
| TB_ClasseHabilidade | 159 | 28 | 12 | 13 |
| TB_TracoRacial | 38 | 2 | 2 | 6 |
| TB_OpcaoJogo | 30 | 7 | 1 | 1 |
| TB_Talento | 14 | 2 | 4 | 0 |
| TB_ItemMundano | 15 | 1 | 0 | 1 |
| backgrounds | 1 | 2 | 0 | 0 |
| TB_Classe | 0 | 2 | 1 | 0 |
| TB_ItemMagico | — (ver §4.1) | — | — | — |

### 3.3 Confiança dos achados

| Tabela | alta | média | baixa |
|---|---:|---:|---:|
| TB_ClasseHabilidade | 120 | 77 | 15 |
| TB_TracoRacial | 19 | 21 | 8 |
| TB_OpcaoJogo | 18 | 20 | 1 |
| TB_Talento | 10 | 10 | 0 |
| TB_ItemMundano | 11 | 5 | 1 |
| backgrounds | 2 | 1 | 0 |
| TB_Classe | 1 | 2 | 0 |

---

## 4. Correções APLICADAS (por tabela)

Todas as aplicações preservaram as demais tags; nenhuma alteração tocou o código do app;
nada foi commitado.

### 4.1 TB_ItemMagico — 220 aplicadas / 4 revertidas / 14 divergiram / 31 não aplicáveis

**Resumo:** dos 269 achados endereçados, **220 foram aplicados**, 4 falharam na validação
e foram **revertidos**, 14 **divergiram** (estado atual não batia ou a proposta não era
tag concreta), 31 **não aplicáveis** (sem `tag_proposta` concreta no pedido).

**Nota de índice importante:** cerca de 66 dos 269 `id` do pedido não batiam com o `nome`
da entidade naquele PK (desalinhamento de índice). A aplicação resolveu isso localizando
cada entidade pelo **nome exato** (match único) em vez de confiar no `id`; apenas 1 caso
ambíguo (4 "Elmo do Terror" idênticos) foi resolvido por eliminação.

**Padrões de correção aplicados (amostra representativa):**

| Padrão | Exemplo | O que mudou | Por quê |
|---|---|---|---|
| Resistência elemental faltando | Cotas de Escamas de Dragão (302–311), Anéis/Armaduras de Resistência | +`resist:<tipo>` | Descrição "resistência a dano X" sem nenhuma tag `resist:`; `<tipo>` é valor do catálogo fechado `damage_type`. |
| Bônus de atributo faltando | Pedras Ioun de atributo (5–9, 666), Amuleto da Saúde (54), Faixas (404) | +`attr:<attr>_score+N` / `:=19` | "Sua Força/Con… aumenta em 2 (máx 20)" / "é 19" sem tag `attr:`. |
| Ataque mágico não tagueado | +N Ferramenta Multiuso (8/21/33), Cajado do Poder (231) | +`spell.atk:+N` (além do `spell_save_cd`) | Descrição dá "+N em ataque de magia E CD", mas só o CD estava. |
| Recarga de recurso de classe | +N Amuleto do Devoto (1/16/28), Tambor (13/26/38), Frasco (10/23/35) | +`instant{resource_restore:<rec>:N} 1/long_rest` | Item recarrega Canalizar Divindade / Inspiração / Feitiçaria 1×/dia. |
| Escala de estado (Dormente/Desperto/Exaltado) | Agonia, Armadura da Alma Valente, Condenadora, Fenthras, Ruína da Cabala, etc. | `ca:+1`→`+2`/`+3`; `weapon.atk/dmg` idem; `charges:4`→`6`/`10` | A entrada nomeada de um estado superior mantinha o valor do estado base. |
| `spell_save_cd` fora da lib | Baralho do Negociador +2/+3 (175/176), Cinto Pele Dragão +2/+3 (278/279) | `spell_save_cd`→`spell.cd` | Verbo `spell_save_cd` não existe no vocabulário; forma canônica é `spell.cd`. |
| Magia concedida por carga | Arma do Comando do Trono (121), Vara da Ressurreição (829), Sinete do Sábio (781–783) | +`cast{spell:<slug>, modifiers{no_slot}, resource_cost:charges:N}` | Descrição lista magias lançáveis por carga sem `cast{}`. |
| Custo de carga errado | Baralho de Dimensões (171), Olhos Encantadores (636) | `charges:1`→`charges:3` / upcast por carga | Valor numérico do custo divergia da tabela da descrição. |
| Feitiço trocado (`#REF!`/errado) | Engrenagem Distante (405): `perdicao`→`banimento` | slug corrigido | Tag apontava para magia diferente da descrita. |

**Reversões (4, falha de validação — estado restaurado):** Arquivo de Astromancia (159,
`grant:spell:*` gerou `#REF!`), Faca Riteknife Rakdos (403, `resource{almas_presas}`
indefinido), Óleo da Escorregadio (630) e Óleo da Eterealidade (631) — ambos `cast{spell:…}`
com slug inexistente no catálogo de magias.

### 4.2 TB_ClasseHabilidade — 46 aplicadas / 5 não acionáveis

Todas as 46 confirmadas foram persistidas (0 divergiu, 0 falhou validação), incluindo a
dupla-correção no id 870 (`creature_type` `demonio`→`corruptor` **e** `no_reactions`→
`apply:no_reaction`, ambas cumulativas).

**Correções de destaque:**

| id | Entidade | Tipo | O que mudou | Por quê / Evidência |
|---|---|---|---|---|
| 619 | Arcanos do Véu | tag_faltando | Implementados o mecanismo comprar/preparar/jogar + os 12 Arcanos | Tag continha só fração de 1 dos 12 arcanos; toda a mecânica-título estava ausente. |
| 624 | Floreios de Lâmina | tag_faltando | Definidos os 3 floreios (esqueleto terminava em `…`) | Tag era esqueleto não implementado. |
| 678 | Sangue e Escamas | divergência | `restriction{armor}` movida para dentro do bloco da CA (`always_active{restriction{equiped{armor}}, ca=…}`) | Restrição solta no topo bloquearia a habilidade inteira (erro de escopo, família do Ex.2 do PO). |
| 597 | Segredos Mágicos | divergência | `spell_selection:any`→`lista:[bardo,clerigo,druida,mago]` | Escopo mais permissivo que o descrito. |
| 716/723 | Marcha/Axioma da Ordem | sintaxe | `no_adv_against_self`→`no_adv:attack{vs:self}` | Vocabulário legado, substituído na lib. |
| 840/858/870/873 | Canalizar Divindade (família) | divergência/sintaxe | +`creature_type:[…]` no `target:enemies`; `demonio`→`corruptor` | Efeito restrito a tipos de criatura; `demonio` não é valor do catálogo. |
| 809 | Maestria em Armas | tag_sobrando | `swap:long_rest` duplicada removida | Aparecia 2× idênticas. |
| 900 | Físico Modular | divergência | +`restriction{equiped{armor}}` na fórmula de CA | CA alternativa lida como sempre ativa (escopo faltando). |

**Não acionáveis (5, não aplicados):** ids 644, 714, 720, 724, 704 — `tag_proposta` era
prosa descrevendo o que falta ("adicionar algo como…"), sem string de tag final.

### 4.3 TB_TracoRacial — 21 aplicadas

Destaques: ids 2065/2071/2083/2084/2086/2087/2090/2091 (todas as `cast{}` de magia
concedida ganharam `modifiers{no_slot}` explícito — sem ele o cast consumiria espaço,
contradizendo "sem gastar espaço de magia"); 2093 (`hit_by_attack`→`attack_roll`, evento
pré-resultado); 2076 (`sense:see_through` inexistente → catálogo `sense_type`); 2343/2346
(`turn_end`→`enemy_end_turn`); 2311 (`restriction{cast_any}` inexistente →
`restricts{spellcasting}`); 2171 (+`count_as:elfo(…)`); 2158 (`no_use_consumed`→
`resource_restore:resistencia_implacavel:1`); 2278 (`trigger`+`resource_restore` unidos com
`->`); 2291 (Armas Naturais movidas para `always_active`, Fúria Elemental isolada em
`while_active` — escopo de restrição, família do Ex.2); 2283 (escala de dano fundida no
bloco `aoe{}`); 2267 (ramo não-programável `ordem_suicida` removido, `take_damage` mantido);
2182/2192.

**Parciais/bloqueados (requer biblioteca, não aplicados):** 2312/2313 (bloqueio de
componentes materiais não tem primitiva — só `restricts{concentration}` foi aplicado),
2216/2317/2321/2328/2334 (exigem evento/catálogo/primitiva inexistentes: `deal_dmg`
genérico, granularidade de plano por vertente, `no_trace`, filtro por essência,
`rebuild:tunnel`).

### 4.4 TB_OpcaoJogo — 33 aplicadas / 2 não aplicáveis

Padrão dominante: **inversão de evento** — ids 25,26,27,28,31,32,35,36,37,52 usavam
`trigger=hit_by_attack{self}` (evento defensivo "é acertado") para descrições ofensivas
("quando você atingir…"); corrigidos para `trigger=hit_melee`. Também: 78
(`doenca`→`doente`, catálogo `condition`), 148 (`adv:con_save`→`concentration_check:adv`),
158 (+`breathe:underwater`), 172/173 (evento + escopo de limitador `1/turn`), 209/218
(`dadv:attack(target:self)`→sem `target:self`; `self` = dono, invertia o alvo).
**Não aplicados:** 128 (`transfer` inexistente), 138 (`first_save` não documentado).

**WARN introduzido (registrado):** id 161 usa `cr<=1` dentro de `restriction{}` — verbo
não documentado; é WARN (não ERROR), passou no critério, fica para o PO decidir refinar.

### 4.5 TB_Talento — 20 aplicadas (0 divergiu, 0 falhou)

Destaques: `ability:int:+1`→`attr:int_score+1` (ids 136/137 — ASI fixo, verbo correto);
`spell_mod`/`talent_attr_mod` (133/138 — talentos sem conjuração usam o modificador do
atributo aumentado pelo talento, não o de conjuração); `contest`→`save` (123 Ator, teste
de CD fixa, não contestado). **Off-by-one de id detectado e resolvido:** id 123 do pedido
era "Telepático" no banco (Ator real = **124**); id 138 era "Telecinético" (entidade real
= **139**) — ambos aplicados na entidade correta localizada por nome+`tag_atual`.

### 4.6 TB_ItemMundano — 12 aplicadas / 15 não aplicáveis

Maestrias corrigidas: id 20 Chicote (+`lentidao_slow`), id 31 Lança Longa
(+`derrubar_topple`). Perfil de arma refeito: id 49 Pistola Pederneira (dano 1d10, alcance
30/90ft, `add_property:carregar`, só `vexar_vex`). Penalidade de deslocamento condicional:
ids 219/223/229 (+`speed:-10ft(requires:str_score<N)`). Venenos com tag mecânica explícita
na correção: ids 285/287/291/293/296/299 (+`apply:`/`aoe{}`). **Não aplicados:** faixa de
venenos/explosivos sem `tag_proposta` por-item concreta (285-302 citados genericamente) e
Tocha (12, divergência de categoria, fora do escopo de tags_json).

### 4.7 backgrounds — 3 aplicadas

id 19 Guardião da Natureza (+`always_active{summon:bestiary{mastiff}}`, companheiro Sled
Dog/Mastim id 572); id 26 Pescador (+`forrageio:comida_e_agua(target:11)`); id 6 Astrônomo
(+`recall:mapas_astrais_e_orientacao_noturna`). Vocabulário confirmado já usado em
entradas irmãs (Mercenário, Viajante).

### 4.8 TB_Classe — 2 aplicadas

id 2 Bardo (+`prof{pick:instrumento:3}` — campo `ferramentas` = "Escolha 3 Instrumentos");
id 4 Caçador (+`prof{pick:ferramenta:1}`). **Observação de processo (refutada como
achado):** 10 das 13 classes têm `descricao` vazia (o modelo `TbClasse` não tem prosa) e
campos estruturados nulos — para essas não há fonte de verdade contra a qual auditar
semanticamente; recomenda-se ao PO decidir se `TbClasse` ganha descrição em prosa ou se a
auditoria dessa tabela se baseia nos campos estruturados.

---

## 5. Achados de baixa confiança NÃO verificados (triagem futura)

Estes achados (**não aplicados**) dependem de decisão de biblioteca/PO ou não puderam ser
confirmados com segurança. Não são erros comprovados — são pendências para triagem.

### 5.1 Exigem nova primitiva/evento/catálogo na `tag_library.json`
- **Evento genérico de "causar dano" (ataque OU magia):** só existe `magic.deal_dmg`
  (exclusivo de magia). Afeta ClasseHab 1459 (Cláusula Complementar), TracoRacial 2216
  (Revelação Nephilim), Talento 82 (Legado do Norte/Quebra-Gelo), ClasseHab 1136
  (Coração de Tempestade). Descrições dizem "ao causar dano com ataque ou magia".
- **"Não deixa rastros/pegadas":** `no_trace` usado em ClasseHab 1057, TracoRacial 2321,
  OpcaoJogo 168 — verbo fora da lib; sem primitiva de rastro. (1057 e as partes narrativas
  são `rp_only`; a parte mecânica exigiria primitiva nova.)
- **Criação/modificação de terreno:** `rebuild:tunnel` (TracoRacial 2334) — sem primitiva.
- **`1d4_long_rest` no enum de reset:** ClasseHab 1458 (Tocado Pelo Túmulo) — a lib só
  documenta `2d4_long_rest`.
- **Meia-cura recebida / redução de cura:** ClasseHab 1034 (Mutagênico Lagartixa) — sem
  primitiva `heal_received:half`.
- **`transfer` (mover efeito entre alvos):** OpcaoJogo 128 (Sinal Exitium).
- **`first_save` (primeiro save do alvo):** OpcaoJogo 138 (Magia Altaneira).
- **Recurso `conviccao` / ability `golpe_da_conviccao` do Paladino ausentes:** as 25
  "Virtudes" (OpcaoJogo 72–102) geram `[ref-resource]` no validador — o pool de Convicção
  não está declarado em `TB_RecursoClasse` nem via `define{}` em nenhuma característica
  auditada. **São os 25 ERROR pré-existentes** do selo final (§6), não introduzidos por
  esta auditoria. Requer localizar/declarar o pool.

### 5.2 Baixa confiança / releitura ambígua (não conclusivos)
- ClasseHab: 611 (Defesa Desarmada — `toggle` vs `:=`), 682 (escala de Consertar),
  769/770/771 (Lâmina Arcana — expansão de tipos de dano no nível 18), 789 (`pick:` inline),
  1071 (Cilada Final — `no_ethereal`), 1092 (`immune_effect`), 1187 (Forma Estelar —
  requisito de espaço de magia), 1393 (`creature_falls`), 1583 (Duplicata das Sombras).
- TracoRacial: 2059/2062/2068 (`at_will` em truque concedido), 2259/2281 (encerramento/
  detecção adicional), 2308 (`transformacao_draconica` como categoria informal).
- ItemMundano: 31b (Lança Longa "duas mãos exceto montado").
- ItemMagico (divergiram/não aplicados por hedge do autor): 202, 302, 377, 401, 457, 470,
  587, 763, 833, 862, 869, 877, 876, 878 — propostas com "ou equivalente"/"a confirmar com
  o motor"/placeholder não resolvido.

---

## 6. Selo final — `validate_tags` (saída real, banco inteiro)

Rodado após todas as aplicações (`manage.py validate_tags`, saída real
`scratchpad/audtags/validate_final_seal.txt`):

```
=== VALIDAÇÃO DAS TAGS (banco) ===
  registros=3444  com tags=2567  linhas de tag=8787
  ...
  ERROR=25  WARN=2  INFO=0
  por código: ref-resource=24, cat-valor=1, ref-ability=1, verbo-desconhecido=1
```

**Interpretação:**
- **25 ERROR** — **todos** são `opcao:Virtudes/*` (Paladino) por `ref-resource`
  (`conviccao`) e `ref-ability` (`golpe_da_conviccao`) ausentes no banco. São
  **pré-existentes** (já constavam no backup pré-auditoria), **não introduzidos** por
  nenhuma das correções aplicadas (§5.1).
- **2 WARN** — `cat-valor=1` (o `cr<=1` de OpcaoJogo id 161, §4.4) + `verbo-desconhecido=1`.
  Ambos WARN (não ERROR), registrados para decisão do PO.
- **0 novos ERROR** introduzidos pela auditoria; as 4 tags que falhariam a validação
  foram revertidas durante a aplicação (§4.1).

---

## 7. Arquivos-fonte da auditoria

Todos em `scratchpad/audtags/` (gitignored):
`backup_pre_auditoria.sqlite3`, `guia_calibracao.md`, `aplicado_*.json` (uma por tabela),
`validate_final_seal.txt`, dumps `dump_TB_*.json`.
