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

➡️ **Regra de ouro: a sincronização de conteúdo TEM que preservar os PKs.** Por isso
usamos **UPSERT por PK** (`loaddata`), **nunca** `TRUNCATE`+reinsert (que renumeraria
os IDs e quebraria todas essas FKs).

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

## Procedimento de deploy

### 0. Backups (a rede de segurança)
- **Produção (obrigatório):** `pg_dump` completo →
  `ref/backups/prod_AAAA-MM-DD.sql`. É o snapshot da "memória" (usuários/missões).
- **Conteúdo (fonte):** já gerado em `ref/backups/conteudo_AAAA-MM-DD.json`
  (`manage.py dump_conteudo`).

### 1. Código + schema
1. `git pull` na produção.
2. `manage.py migrate` → aplica 0014–0032 (ADITIVO: cria tabelas novas e colunas
   novas; **não apaga dado**). É o `start_server.bat`/`sync_db.bat` já faz isso.

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
