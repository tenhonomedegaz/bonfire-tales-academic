# Deploy: sincronizar CONTEÚDO sem prejudicar usuários/missões

Objetivo: levar o **catálogo do jogo** que editamos no banco de trabalho para a
**PRODUÇÃO** (PostgreSQL), **sem tocar** na "memória" da produção
(usuários, personagens, missões, mercado, jornal/crônicas).

## Política de versionamento (2026-07-20): restores NÃO vão mais pro git

Os artefatos `ref/backups/restore_consolidado_<timestamp>.json` (+ `.report.json`)
**não são versionados no git**. O deploy do merge de conteúdo é um **upload local no
console do admin** — o arquivo nunca precisa estar no repositório para a produção
enxergá-lo:

1. Gere o arquivo **no dev** (`ref/` já é gitignored — o `.json` fica só no disco local).
2. No **console do admin da produção**, use a ação **"Merge de conteudo (dev ->
   producao)"** (`action=merge_conteudo` em `home/admin.py`) e faça o **upload manual**
   desse `.json` pelo campo de arquivo. Esse fluxo casa por chave natural (slug) via
   `home.deploy_sync.sincronizar_conteudo` — não precisa de `git pull`/`loaddata` para o
   conteúdo chegar lá.
3. O **único artefato que continua versionado** é o **relatório em Markdown**
   (`docs/agentes/relatorio_restore_<timestamp>.md`), que documenta o que mudou, os
   números por tabela e o passo a passo de aplicação/rollback — serve de histórico e
   auditoria sem inflar o diff do repo com dezenas de milhares de linhas de JSON.
4. Ao gerar uma nova rodada, **apague (não apenas destracka)** o par
   `restore_consolidado_*.json`/`.report.json` da rodada anterior do disco (fica
   superseded) e mantenha só o relatório `.md` correspondente no git — os relatórios
   anteriores também podem ser removidos do git quando um relatório `FINAL` mais novo os
   substitui integralmente.

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
Item, Magia, Pericia, Personalidade, Proficiencia, Recurso, Talento e o ledger
TbPersonagemAventura); TbTransacao,
TbTransacaoMestre, TbAventuraMestre (missões); TbAnuncioItemMagico (mercado);
TbCronica, TbJornal; TbReiDaColina; auth (User/Session). Não entram no fixture → ficam
intactas.

### C) Bot (Discord) — fora do escopo Django
Bot* são `managed=False` (tabelas `transactions`, `discord_subscribers`, etc.,
COMPARTILHADAS com o bot). Nunca tocar via Django.

### D) Política atual (2026-08-13) — conteúdo compartilhado e mundo
- **TbBestiario / TbArmadilha**: sincronizar somente os registros oficiais
  (`comunidade=False`, autor nulo), preservando por slug os IDs oficiais existentes.
  Registros comunitários da produção nunca entram no fixture e são protegidos por
  assinatura antes/depois do merge.
- **TbMapLayer / TbRegiao / TbTerritorio / TbOrganizacao / TbMapMarker /
  TbMapDesenho**: produção vence. São dados autorais editados pela staff e ficam fora
  do merge mecânico.

## Aplicação recomendada

Há dois caminhos que usam o mesmo núcleo seguro por chave natural:

1. **Upload manual:** no console do admin, ação **Merge de conteúdo (dev ->
   produção)**. É o caminho dos arquivos `restore_consolidado_*.json`.
2. **Fixture versionado:** depois do `git pull` e das migrations, executar:

```
deploy_conteudo.bat
```
ou
```
manage.py migrate && manage.py sync_conteudo
```

`sync_conteudo`/`merge_conteudo` (por CHAVE NATURAL) faz tudo com segurança: (1) backup da memória em
`backups/` (restaurável com `loaddata`); (2) **upsert por slug** das tabelas referenciadas
por usuário (preserva o PK da prod); (3) **substitui inteiras** as demais (delete+reinsert,
remapeando FKs de pai); (4) aplica deleções explícitas versionadas em
`home/content_deletions.json` somente quando não há FK de memória bloqueando; (5) realinha as sequences; (6) confirma que as tabelas de
usuário/missão, mapa/wiki e conteúdo comunitário ficaram com a MESMA contagem e a
MESMA assinatura SHA-256. Use `--dry-run` p/ ver o plano (quantos
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

### Renomeações de slug

Quando a identidade canônica de um conteúdo muda, o registro antigo da produção não
deve ser apagado nem inserido novamente: isso quebraria ou duplicaria referências de
personagens e do mercado. Registre a troca em `home/content_renames.json`:

```
{
  "TbItemMagico": {
    "Tiara-do-Intelecto": "tiara-do-intelecto"
  }
}
```

O merge localiza o slug antigo, atualiza o mesmo registro com os dados atuais e preserva
seu PK. Se os slugs antigo e novo já coexistirem na produção, a operação é abortada para
que a duplicidade seja examinada em vez de mesclada silenciosamente. O código contendo
essa regra precisa estar publicado antes do upload do restore que usa a renomeação.

## Procedimentos proibidos para fixture de conteúdo

- Não usar `loaddata` diretamente: PKs de dev e produção podem representar slugs
  diferentes.
- Não enviar fixture mecânico no painel **Restauração de backup**, que grava por PK.
- Não incluir mapa/wiki em um merge mecânico. O mundo é produção-vence.

O painel de restauração por PK possui um guard para recusar fixtures compostos apenas
por catálogo ou mundo, mas o procedimento correto continua sendo o merge por chave
natural.

## Resumo das mudanças desta leva
- **Schema (migrations 0014–0032):** tabelas novas (Bestiário, Condição/Idioma/Regra,
  Anúncio, Armadilha, Transação, RecompensaMestre, AventuraMestre/TransaçãoMestre,
  PersonagemAtributoBonus) + colunas novas (TbPersonagem, TbPersonagemItem,
  TbItemMundano, TbAntecedente, TbRecursoclasse, UserProfile). Tudo aditivo.
- **Conteúdo (dados):** magias (nomes), talentos e traços raciais (tags/descrições),
  classes (proficiências), habilidades de classe, opções, condições/idiomas/regras,
  itens. Tudo em `home.tag_library.json` (verbos `trocavel`, `extinguish`) é arquivo,
  vai no git normalmente.
