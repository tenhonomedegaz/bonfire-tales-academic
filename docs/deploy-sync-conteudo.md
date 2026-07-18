# Deploy: sincronizar CONTEÚDO sem prejudicar usuários/missões

Objetivo: levar o **catálogo do jogo** que editamos no banco de TRABALHO (SQLite de
dev) para a **PRODUÇÃO** (PostgreSQL), **sem tocar** na "memória" da produção
(usuários, personagens, missões, mercado, jornal/crônicas).

## Por que é delicado (o ponto de risco)

Os dados de USUÁRIO referenciam o CONTEÚDO **por PK (id)**:
`TbPersonagemMagia.id_magia → TbMagia`, `TbPersonagemTalento.id_talento → TbTalento`,
`TbPersonagem.id_raca/id_linhagem/id_essencia/id_antecedente`,
`TbPersonagemClasse.id_classe/id_subclasse`, `TbPersonagemItem.id_item_magico`,
`TbPersonagemEscolha.id_opcao`, `TbAnuncioItemMagico.id_item_magico`.

➡️ **Os PKs do catálogo DESALINHARAM entre dev e produção** (ex.: `pk=1596` é "Frenesi"
do Bárbaro no dev e "Conjuração" de um conjurador na prod). Carregar por PK (`loaddata`)
poria o conteúdo errado em cima do registro errado. Por isso a sync é por **CHAVE NATURAL**:
- Tabelas referenciadas por FK de usuário (todas têm **slug único**): match por slug →
  ATUALIZA o registro da prod **preservando o PK dela** (a FK do personagem continua válida).
- Demais tabelas (ninguém referencia por PK): **substitui inteiras** (delete+reinsert),
  remapeando as FKs de pai do PK-dev para o PK-prod.

## Classificação das tabelas

### A) CONTEÚDO — sincroniza do SQLite (as "tabelas que trabalhamos")
TbRaca, TbLinhagem, TbEssencia, TbAntecedente, TbClasse, TbSubclasse,
TbClassehabilidade, TbRecursoclasse, TbOpcaojogo, TbAcessoopcao, TbMagia, TbTalento,
TbTracoracial, TbItemMagico, TbItemMundano, TbCondicao, TbIdioma, TbRegra,
TbRecompensaMestre. → `manage.py dump_conteudo`.

### B) USUÁRIO / RUNTIME — NUNCA sobrescrever (a "memória")
UserProfile; TbPersonagem + todas as TbPersonagem* (AtributoBonus, Classe, Escolha,
Item, Magia, Pericia, Personalidade, Proficiencia, Recurso, Talento); TbTransacao,
TbTransacaoMestre, TbAventuraMestre (missões); TbAnuncioItemMagico (mercado);
TbCronica, TbJornal; TbReiDaColina; auth (User/Session). Não entram no fixture → ficam
intactas.

### C) Bot (Discord) — fora do escopo Django
Bot* são `managed=False` (tabelas `transactions`, `discord_subscribers`, etc.,
COMPARTILHADAS com o bot). Nunca tocar via Django.

### D) Decidido pelo PO (2026-06-26) — entram no conteúdo
- **TbBestiario / TbArmadilha**: sincronizar **inteiros**. (Hoje os 28 bestiários são
  todos oficiais — autor nulo — e Armadilhas está vazia, então não há conteúdo de
  comunidade na produção a preservar. ⚠️ Se no futuro houver itens de comunidade na
  prod, revisar para `--bestiario-oficial`, senão eles seriam sobrescritos.)
- **TbRegiao / TbTerritorio / TbMapMarker**: sincronizar do dev (fonte de verdade = dev).

Ambos já estão em `CONTENT_MODELS` do `dump_conteudo` (24 modelos, ~4118 registros).

## Deploy de UM COMANDO (recomendado)

O fixture vai **no git** (`home/fixtures/conteudo.json` + `conteudo_manifest.json`), então
na produção basta, após `git pull`:

```
deploy_conteudo.bat
```
ou
```
manage.py migrate && manage.py sync_conteudo
```

`sync_conteudo` (por CHAVE NATURAL) faz tudo com segurança: (1) backup da memória em
`backups/` (restaurável com `loaddata`); (2) **upsert por slug** das tabelas referenciadas
por usuário (preserva o PK da prod); (3) **substitui inteiras** as demais (delete+reinsert,
remapeando FKs de pai); (4) aplica deleções explícitas versionadas em
`home/content_deletions.json` somente quando não há FK de memória bloqueando; (5) realinha as sequences; (6) confirma que as tabelas de
usuário/missão ficaram com a MESMA contagem. Use `--dry-run` p/ ver o plano (quantos
atualizar/inserir/substituir) sem alterar nada.

Para gerar/atualizar o fixture (no dev, antes de commitar): `manage.py dump_conteudo
--output home/fixtures/conteudo.json --manifest home/fixtures/conteudo_manifest.json`.

## Procedimento seguro quando existe backup fresco da produção

Quando houver um `backup_completo_<timestamp>.json` recém-baixado da produção, primeiro
rebaseie o banco local nele e só então gere o fixture. Isso evita sobrescrever conteúdo
que não foi alterado na dev com uma versão local velha.

```
manage.py migrate
manage.py restore_full_backup_local --file ref/backup_completo_YYYYMMDD_HHMMSS.json --confirm RESTAURAR_LOCAL
manage.py sync_conteudo
manage.py dump_conteudo --output home/fixtures/conteudo.json --manifest home/fixtures/conteudo_manifest.json
manage.py sync_conteudo --dry-run
```

O resultado é um `conteudo.json` baseado no backup fresco da produção mais as mudanças
de conteúdo da dev. Dados de usuário/runtime não entram no fixture.

### Deleções explícitas

Tabelas referenciadas por personagem/usuário usam upsert por slug e preservam PKs.
Por segurança, um registro ausente no fixture **não é deletado automaticamente**.
Conteúdo removido de propósito deve ser listado em `home/content_deletions.json`.

Exemplo:

```
{
  "TbMagia": ["sacrificio-de-sangue"]
}
```

Durante o sync, a deleção só acontece se o registro não estiver referenciado por tabelas
de memória. Se houver referência, o relatório mostra a deleção como bloqueada.

## Procedimento manual (passo a passo, equivalente)

### 0. Backups (a rede de segurança)
- **Produção (obrigatório):** `pg_dump` completo →
  `ref/backups/prod_AAAA-MM-DD.sql`. É o snapshot da "memória" (usuários/missões).
- **Conteúdo (fonte):** já gerado em `ref/backups/conteudo_AAAA-MM-DD.json`
  (`manage.py dump_conteudo`).

### 1. Código + schema
1. `git pull` na produção.
2. `manage.py migrate` → aplica 0014–0032 (ADITIVO: cria tabelas novas e colunas
   novas; **não apaga dado**). É o que o `start_server.bat` já faz automaticamente.

### 2. Checagem de alinhamento de PK (antes de carregar!)
O `loaddata` só é seguro se cada PK de conteúdo aponta para o MESMO registro nos dois
bancos. Gere o manifesto nos dois e compare:
```
# no dev (SQLite):
POSTGRES_URL="" manage.py dump_conteudo --manifest ref/backups/manifest_local.json
# na produção:
manage.py dump_conteudo --manifest manifest_prod.json
# comparar: para cada modelo, pk->chave-natural deve bater. Divergência = NÃO carregar.
```
Se houver divergência de PK, NÃO usar loaddata cego — sincronizar por chave natural
(slug/nome) só nos campos editáveis.

### 3. Carregar o conteúdo na produção
```
manage.py loaddata ref/backups/conteudo_AAAA-MM-DD.json
```
Faz UPDATE dos registros existentes (por PK) e INSERT dos novos, em transação. As
tabelas de usuário não estão no fixture → intactas.

### 4. Resetar sequências de PK (PostgreSQL)
Depois do loaddata, alinhe os sequences para inserts futuros não colidirem:
```
manage.py sqlsequencereset home | manage.py dbshell
```

### 5. Verificar
- Contagens das tabelas de conteúdo conferem com o dev.
- Spot-check: um talento/traço editado aparece com a tag/descrição nova.
- `TbPersonagem`/`UserProfile`/transações com a MESMA contagem de antes (memória intacta).

## Resumo das mudanças desta leva
- **Schema (migrations 0014–0032):** tabelas novas (Bestiário, Condição/Idioma/Regra,
  Anúncio, Armadilha, Transação, RecompensaMestre, AventuraMestre/TransaçãoMestre,
  PersonagemAtributoBonus) + colunas novas (TbPersonagem, TbPersonagemItem,
  TbItemMundano, TbAntecedente, TbRecursoclasse, UserProfile). Tudo aditivo.
- **Conteúdo (dados):** magias (nomes), talentos e traços raciais (tags/descrições),
  classes (proficiências), habilidades de classe, opções, condições/idiomas/regras,
  itens. Tudo em `home.tag_library.json` (verbos `trocavel`, `extinguish`) é arquivo,
  vai no git normalmente.
