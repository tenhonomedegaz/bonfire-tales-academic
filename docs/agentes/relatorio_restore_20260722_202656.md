# Restore de conteúdo prod (dev-vence) — 2026-07-22 20:26:56 — 3ª LEVA DA STAFF + PALADINO PREPARADO DE VERDADE

- **Arquivo de restauração:** `ref/backups/restore_consolidado_20260722_202656.json` (5011 registros, 21 modelos de conteúdo)
- **Relatório de máquina:** `ref/backups/restore_consolidado_20260722_202656.report.json`
- **SHA-256 do arquivo (bytes em disco, CRLF puro):** `874c52080bec000842693e512a6ad84f46d5e30352ee2cfce61261a722f3282d`
- **Fonte:** DEV (`db.sqlite3`) via ORM, Postgres desligado.
- **Base da análise (baseline):** `restore_consolidado_20260721_000606.json` — **esta versão o supersede**.
- **Rollback:** `ref/Characterbuilder testes/backup_completo_20260718_015031.json` (restore_backup por PK) ou o backup fresco do passo 2 abaixo.

> **POLÍTICA DE ENTREGA (PO):** o `.json` e o `.report.json` ficam **SÓ NO DISCO** em
> `ref/backups/` (pasta **gitignored**) — **não são commitados** e **não** entram com `git add -f`.
> O PO sobe o `.json` pelo console de admin. **Só este relatório `.md` é versionado.**

## Painel de Merge (como o `sincronizar_conteudo` classifica)

- **UPSERT por slug (preserva o PK da produção):** `TbRaca, TbLinhagem, TbEssencia,
  TbAntecedente, TbClasse, TbSubclasse, TbOpcaojogo, TbMagia, TbTalento, TbItemMagico,
  TbCosmetico`. Casa por `slug`, atualiza os campos, mantém o ID que a memória referencia.
  (`TbConquista` está na lista mas tem 0 linhas no dev → ausente do fixture.)
- **SUBSTITUI (delete-all + reinsert com o PK do dev):** `TbClassehabilidade, TbRecursoclasse,
  TbAcessoopcao, TbTracoracial, TbCondicao, TbIdioma, TbRegra, TbRecompensaMestre,
  TbItemMundano, TbBestiario`. (`TbArmadilha` está na lista mas tem 0 linhas → ausente → tabela
  preservada na prod.)
- **FORA do arquivo (de propósito):** `TbRegiao, TbTerritorio, TbMapMarker, TbMapDesenho`
  (mundo/mapa — prod vence, preservado por ausência), `TbOrganizacao` e `TbMapLayer` (fora de
  qualquer lista de sync) e **toda a memória** (usuários, personagens, transações, bot). O
  aplicador **pula e preserva** qualquer modelo ausente no fixture.

## O que mudou nesta versão (vs baseline `20260721_000606`)

Esta leva é **quase toda de motor/JS** (criador, level-up, derive) — o **catálogo** mexeu só no
mínimo necessário para o **Paladino virar conjurador PREPARADO** e para os dois **bugs de conteúdo**
da 3ª leva. **Δ de LINHA = −1** (um recurso do Paladino apagado); as outras 20 tabelas de conteúdo
têm **0 mudança de linha**. **4 tabelas** mudam de `sha256_registros`:

| Tabela | pk | Natureza da mudança |
|---|---|---|
| **TbClasse** | 13 (Paladino) | `tags_json`: spellcasting `prepara:conhecidas → prepara:preparadas` + `prep_limite:cha_mod+rounddown(classlvl/2)` (fórmula da descrição — CAR + metade do nível). |
| **TbClassehabilidade** | 1626 (Conjuração, Paladino) | mesma troca de spellcasting (`preparadas` + `prep_limite`) **e remove `swap:level_up`** — conjurador preparado **não troca** magias conhecidas, então o passo de swap dele **some por consequência**. |
| **TbClassehabilidade** | 1077 (Domínio da Caçada, capstone Caçador) | `descricao`: desembrulha `[Golpe Certeiro](tbMagia, golpe-certeiro)` e `[ataque extra]` de volta a texto puro (migração **0065**) — o card não puxa mais a MAGIA homônima. |
| **TbTalento** | 3 (Brigão de Taverna) | `descricao`: desembrulha `[Golpe Certeiro](tbMagia, golpe-certeiro)` a texto puro (migração **0065**). `tags_json` **inalteradas** — o **+1 estático** do desarmado quando o dado já é `1d6+` é **lógica de motor** (`character_engine.py`), não dado. |
| **TbRecursoclasse** | 3774 (Magias Conhecidas, Paladino) | **REMOVIDO** — coluna equivocada de "magias conhecidas"; conjurador preparado não tem contagem de conhecidas. **Única mudança de LINHA** (135 → 134). |

> **Vampiro / maestria / idioma / lint** desta leva são **100% motor/JS/teste** e **não tocam o
> catálogo**: herança de clã selecionável, exclusão mútua, Percepção indicada, talentos por clã no
> pool, cross-lock de idioma (cliente **e** servidor), maestria repetível por arma entre slots, e o
> lint permanente de templates (`{# #}` multilinha reprova em teste). Por isso **não aparecem** no
> diff de conteúdo.

## Diff de contagens vs report do `20260721_000606` — explicação de CADA linha

**Δ de LINHAS = −1 (só TbRecursoclasse).** As demais 20 tabelas de conteúdo: 0 linha. Só há Δ de
VALOR (mesma contagem) em TbClasse, TbTalento e TbClassehabilidade.

| Tabela | Ação | Baseline (000606) | Neste arquivo / pós | Δ linhas | Explicação |
|---|---|---:|---:|---:|---|
| TbRaca | upsert_slug | 4 | 4 | 0 | — |
| TbLinhagem | upsert_slug | 16 | 16 | 0 | — |
| TbEssencia | upsert_slug | 4 | 4 | 0 | — |
| TbAntecedente | upsert_slug | 30 | 30 | 0 | — |
| **TbClasse** | upsert_slug | 13 | 13 | **0** | **valor: pk13 Paladino → prepara:preparadas + prep_limite** |
| TbSubclasse | upsert_slug | 111 | 111 | 0 | — |
| TbOpcaojogo | upsert_slug | 259 | 259 | 0 | — |
| TbMagia | upsert_slug | 580 | 580 | 0 | — |
| **TbTalento** | upsert_slug | 139 | 139 | **0** | **valor: pk3 Brigão descrição desembrulhada (0065)** |
| TbItemMagico | upsert_slug | 953 | 953 | 0 | — |
| TbCosmetico | upsert_slug | 24 | 24 | 0 | — |
| **TbClassehabilidade** | substitui | 884 | 884 | **0** | **valor: pk1626 Conjuração (preparadas, −swap) + pk1077 Caçador (0065)** |
| **TbRecursoclasse** | substitui | 135 | **134** | **−1** | **delete pk3774 "Magias Conhecidas" do Paladino (prepared caster)** |
| TbAcessoopcao | substitui | 88 | 88 | 0 | — |
| TbTracoracial | substitui | 352 | 352 | 0 | — |
| TbCondicao | substitui | 28 | 28 | 0 | — |
| TbIdioma | substitui | 22 | 22 | 0 | — |
| TbRegra | substitui | 139 | 139 | 0 | — |
| TbRecompensaMestre | substitui | 9 | 9 | 0 | — |
| TbItemMundano | substitui | 302 | 302 | 0 | — |
| TbBestiario | substitui | 920 | 920 | 0 | — |
| TbConquista / TbArmadilha | 0 → ausente | — | preservado | — | 0 linhas no dev |
| TbRegiao / TbTerritorio / TbMapMarker / TbMapDesenho | skip/preserva | — | 74/35/74/1 | fora | mundo/mapa — prod vence |
| TbOrganizacao / TbMapLayer | fora do sync | — | 81 / 4 | fora | nunca tocados |

**Total no arquivo: 5011 registros / 21 modelos** (5012 → 5011, exatamente o −1 do recurso do
Paladino). **Nenhum diff de linha inexplicado.**

**Tabelas com `sha256_registros` ALTERADO vs 000606 (apenas 4):** `TbClasse, TbTalento,
TbClassehabilidade, TbRecursoclasse`. As outras **17 tabelas com linhas batem `sha256_registros`
EXATAMENTE** com o report do 000606 (prova de que só as mudanças intencionais entraram).

## Validação já executada (independente)

`json.load` → `deserialize` completo → aplicação em `transaction.atomic()` **revertida (rollback)**
sobre o próprio `db.sqlite3` do dev — **nada persistido** (pré == pós confirmado):

- **Bytes em disco:** SHA-256 do arquivo (`certutil` independente) == `sha256_arquivo` do report
  (**match**: `874c52080bec000842693e512a6ad84f46d5e30352ee2cfce61261a722f3282d`). CRLF puro
  (233134 pares CRLF, **0** LF solto), **sem BOM**, UTF-8 cru.
- **`json.load`:** 5011 registros == `final_records`. **`deserialize`:** 5011 objetos, 21 modelos.
- **Memória intacta:** `mem_ok=True`; contagem pré == pós tanto na memória (21 tabelas) quanto no
  conteúdo.
- **Mapa preservado:** `pass2_skipped = [TbRegiao, TbTerritorio, TbMapMarker, TbArmadilha,
  TbMapDesenho]` — mundo/mapa entram por **ausência** no fixture (prod vence, 74/35/74/1 intactos).

Spot-checks no fixture (bytes em disco) — **todos OK**:

- **Paladino** (TbClasse pk13 **e** Conjuração pk1626): `prepara:preparadas, foco:simbolo_sagrado,
  prep_limite:cha_mod+rounddown(classlvl/2)` presente **2×**; **nenhum** `lista:paladino,
  prepara:conhecidas` restante.
- **Recurso "Magias Conhecidas" do Paladino** (id_classe=13): **ausente** do arquivo.
- **Golpe Certeiro:** **nenhuma** ocorrência de `(tbMagia, golpe-certeiro)` no fixture.
- **Clérigo** (Conjuração pk1086): `lista:clerigo, prepara:conhecidas` **preservado** (não era
  alvo — só o Paladino virou preparado).

---

## CHECKLIST DO DEPLOY (ordem obrigatória)

> **Restore CONSOLIDADO (dev-vence, catálogo inteiro).** Se o deploy anterior (`000606`) ainda não
> foi aplicado, **este arquivo engloba tudo** — basta **UM merge só**. Ele carrega todo o cumulativo
> (sintonias/homebrew/avental/brigão-luchador do 000606 **+** Paladino preparado **+** golpe-certeiro).

### 1. `force_update.bat` — PRIMEIRO

Roda `git reset --hard origin/dev` e **aplica as migrações** em produção **ANTES** de qualquer
merge. A mais nova é **`0065_fix_ref_golpe_certeiro`** (data-migration que desembrulha o card
espúrio de "Golpe Certeiro" em `TbTalento`/`TbClassehabilidade`); já inclui **0063** (remove
`subclasses` de `TbMagia`) e **0064** (`concedido_por` em `TbPersonagemItem`) das levas anteriores.
**Confirme que aplicaram até a 0065 sem erro.**

### 2. Baixe o backup completo pelo console

Ação **"Baixar backup"** (`download_backup_view`) do admin. **Guarde-o** — é o rollback real do
momento, tirado **depois** das migrações.

### 3. Merge de conteúdo com o `restore_consolidado_20260722_202656.json`

No console do admin, ação **"Merge de conteudo (dev -> producao)"** (`action=merge_conteudo`),
**NÃO** "Restauração de backup". Faça upload do `restore_consolidado_20260722_202656.json` **subido
do disco do dev** (`ref/backups/`, gitignored — não está no repositório).

> O painel "Restaurar backup" (upsert por PK) **FALHA** com este fixture (colisão de slug único —
> PKs de dev/prod desalinhados); o guard em `home/admin.py` recusa. Use **exclusivamente o merge por
> slug**. Ele faz UPSERT por slug (preserva PK), SUBSTITUI (delete+reinsert), pula os modelos
> ausentes (mapa/mundo) e roda `sqlsequencereset` no fim (PASSO 3, só Postgres).

**Leia o relatório na tela:** deve terminar com "MEMÓRIA INTACTA: 21 tabelas…" e listar
`TbRegiao/TbTerritorio/TbMapMarker/TbArmadilha/TbMapDesenho` em "Tabelas preservadas por ausência no
fixture". **Confira as contagens** — todas idênticas ao 000606 **exceto** `home.tbrecursoclasse=134`
(era 135). Confira ainda `home.tbclasse=13`, `home.tbtalento=139`, `home.tbclassehabilidade=884`. Se
disser "ATENÇÃO: memória mudou!", **pare** e faça rollback.

### 4. Rollback (se algo sair errado)

Ação **"Restauração de backup"** com upload do backup do **passo 2** (preferível) ou, na falta,
**`ref/Characterbuilder testes/backup_completo_20260718_015031.json`**. Faz upsert por PK + realinha
sequences, revertendo só o catálogo (memória e mapa não foram tocados).

### 5. Ajuste MANUAL na prod (item que o merge não cobre)

- **Escudo do Scar:** trocar o item do inventário para **`+1 Escudo (*)`** (resultando em **CA 20**).
  É **memória de personagem** (inventário) — o deploy de catálogo **não** toca; ajuste na ficha dele
  à mão.

### 6. Smoke-test da 3ª leva (na prod, depois do merge)

- **Marca sem conjuração:** a lista expandida de magias de Marca só aparece para quem **conjura de
  verdade**; sem conjuração, **só as diretas** (respeitando o teto da tabela de slots).
- **Cavaleiro Arcano (EK):** no level-up **escolhe truque** e **magia até o teto** da classe.
- **Paladino:** **prepara** magias (limite **CAR + metade do nível**, arredondado p/ baixo) e **não
  tem passo de swap** (conjurador preparado não troca conhecidas).
- **Maestria:** a **mesma arma** pode repetir em **2 slots**; o par **arma+maestria** é que não
  repete.
- **Vampiro:** herança de clã selecionável — testar **Sybaris** (exclusão mútua com o outro clã,
  Percepção indicada, talentos do clã no pool).
- **Idioma:** idioma já ganho por raça/antecedente **não repete** no seletor (trava no cliente **e**
  no servidor).
- **Wizard/level-up:** sem **texto vazado** de `{# … #}` (o lint de templates reprova isso em teste).
- **Scar desarmado (Brigão N-alto):** ataque **+11** e dano **`1d10 +8`** — o +1 estático entra
  porque o dado do desarmado já é `1d6+` (a planilha antiga subcontava).

---

## Decisões do PO ainda pendentes (herdadas)

1. **Mapa/mundo/organizações:** confirmar **PROD VENCE** e retirar `TbRegiao/TbTerritorio/
   TbMapMarker/TbMapDesenho` da lista `SUBSTITUI` em `home/deploy_sync.py` (hoje só ficam a salvo por
   estarem ausentes do fixture).
2. **`TbMapLayer` camada 1 `publica`:** prod=True vs dev=False. Fora.
3. **`TbConquista` vazia no dev (0)** apesar do seed 0052 — popular antes se o catálogo deve existir.
4. **Linha órfã do Avental** (herdada do 000606): o merge insere `avental-de-acougueiro` e não
   remove `babador-de-acougueiro` (sem tombstone); limpeza manual opcional na prod.
