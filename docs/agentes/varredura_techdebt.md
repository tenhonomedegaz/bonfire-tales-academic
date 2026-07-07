# Varredura de Tech-Debt — BonfireSite

Relatorio consolidado de achados **confirmados** (verificados adversarialmente). Todos os itens abaixo foram validados no codigo; nenhum e especulativo. Severidades: **critica** (agir ja) -> **alta** -> **media** -> **baixa** (higiene).

---

## Tabela geral priorizada

| # | Item | Arquivo:linha | Severidade | Acao sugerida |
|---|------|---------------|-----------|---------------|
| 1 | `DEBUG` com default `True` (defeito-raiz) | `bonfire/settings.py:63` | **critica** | Trocar default para `False` (fail-safe) |
| 2 | `SECRET_KEY` com fallback `django-insecure-...` commitado | `bonfire/settings.py:57-60` | **critica** | Remover fallback; `ImproperlyConfigured` se ausente em prod |
| 3 | Console de servidor com RCE `shell=True` atras de hash publico | `home/admin.py:285` | **critica** | Sem fallback de senha; revisar necessidade do console |
| 4 | `SERVER_LOGS_PASSWORD_HASH` hardcoded (par do #3) | `bonfire/settings.py:275` | **alta** | Remover fallback; exigir env |
| 5 | `ALLOWED_HOSTS` vira `['*']` sob DEBUG (encadeia com #1) | `bonfire/settings.py:70-71` | **alta** | Corrigido ao arrumar #1; nao depender de DEBUG |
| 6 | Cookies nunca `Secure` se prod nao setar `DJANGO_DEBUG=false` | `bonfire/settings.py:217-218` | **alta** | Corrigido ao arrumar #1 |
| 7 | `/media/` nao servido em prod (`DEBUG=False`) | `bonfire/urls.py:12-13` | **alta** | Servir via nginx/Cloudflare ou WhiteNoise p/ MEDIA |
| 8 | `media/` com uploads reais de usuario (PII) untracked, nao ignorado | `media/` (`settings.py:197`) | **alta** | Adicionar `media/` ao `.gitignore` |
| 9 | `backup_sqlite.json` (~10.5 MB) na raiz, nao ignorado | `backup_sqlite.json` | **alta** | Ignorar ou mover para `backups/` |
| 10 | `conteudo.json` (~9.9 MB) na raiz, nao ignorado | `conteudo.json` (raiz) | **alta** | Ignorar (fixture legitimo e `home/fixtures/conteudo.json`) |
| 11 | `taggear_itens.py` quebra ao re-executar (le colunas removidas 0043) | `home/management/commands/taggear_itens.py:251-294` | **alta** | Arquivar ou migrar leitura p/ `tags_json` |
| 12 | `refinar_itens_mundanos_csv.py` quebra ao re-executar (colunas 0043) | `home/management/commands/refinar_itens_mundanos_csv.py:569-688` | **alta** | Arquivar (one-shot ja cumprido) |
| 13 | `CSRF_TRUSTED_ORIGINS` confia em `*.trycloudflare.com` por default | `bonfire/settings.py:203-210` | **media** | Remover tunel de dev do default de prod |
| 14 | Templates orfaos `classes.html` e `racas.html` (contexto descasado) | `home/templates/home/pages/classes.html:1`, `racas.html:1` | **media** | Remover (sobra do commit 3cfb483) |
| 15 | `parchment-texture.jpg` inexistente -> hero da 404 | `home/templates/home/pages/jornal_list.html:7` | **media** | Adicionar o asset ou corrigir o `{% static %}` |
| 16 | Modulo `google_docs_import.py` 100% morto | `home/google_docs_import.py:1-289` | **media** | Remover modulo inteiro |
| 17 | Views adaptador legado mortas + mappers so por elas | `home/views.py:1275,1622,2002,2019,459` | **media** | Remover ramo adaptador legado abandonado |
| 18 | Modelo `TbPersonagemPersonalidade` (schema morto) | `home/models.py:1363-1370` | **media** | Avaliar remocao (tabela sincronizada, sem feature) |
| 19 | `importar_livros.py` allowlist com colunas removidas (bug latente) | `home/management/commands/importar_livros.py:23-27` | **media** | Podar chaves mortas da allowlist |
| 20 | Cadeia de 46 migracoes longa — candidata a `squashmigrations` | `home/migrations/0001-0046` | **media** | Squash ate marco estavel (revisar RunPython) |
| 21 | Data-migration `background_grants` = regra de catalogo em migracao | `home/migrations/0035_tbantecedente_background_grants.py:13-40` | **media** | Considerar seed/management command |
| 22 | Data-migrations irreversiveis de CA (`reverse=pass`) | `home/migrations/0042...py:8-32`, `0044...py:15-50` | **media** | Documentar ponto-de-nao-retorno (0043 remove colunas) |
| 23 | `batch_save_error.log` via `open(...,'w')` + `print` no except | `home/views.py:6063-6065` | **media** | Trocar por `logging.getLogger` |
| 24 | Gate `is_superuser` triplicado verbatim (camadas do mapa) | `home/views.py:8350,8393,8432` | **media** | Extrair decorator/helper compartilhado |
| 25 | Conversao PO/PP/PC duplicada inline | `home/character_engine.py:1730` (vs `views.py:2894-2906`) | **media** | Extrair helper de divisao |
| 26 | Arquivos scratch `qc`/`query`/`start` commitados (19 bytes cada) | raiz (`git ls-files`) | **media** | `git rm` os tres |
| 27 | Assets pesados `SKARNER *.png` untracked em `docs/agentes/` | `docs/agentes/SKARNER IMAGEM.png`, `SKARNER TOKEN.png` | **media** | Ignorar ou nao commitar (~3.4 MB) |
| 28 | CSS orfaos `index.css` / `legado_collection_detail.css` / `legado_document_form.css` | `home/static/css/pages/` | **baixa** | Deletar (ja marcados como orfaos no doc de arquitetura) |
| 29 | Imagem orfa `pena_branca.png` | `home/static/assets/pena_branca.png` | **baixa** | Deletar (so `pena_preta.png` e usada) |
| 30 | Imports mortos em `views.py` (`DjangoJSONEncoder`, `escape`) | `home/views.py:16,27` | **baixa** | Remover imports nao usados |
| 31 | Imports mortos em `admin.py` (`math`, `urlencode`, `validate_json_no_sql_danger`) | `home/admin.py:2,8,56` | **baixa** | Remover imports nao usados |
| 32 | Imports mortos em modulo morto (`os`, `json`) | `home/google_docs_import.py:8,13` | **baixa** | Cai junto com o modulo (#16) |
| 33 | `gunicorn` em `requirements.txt` nunca usado (deploy = waitress) | `requirements.txt:2` | **baixa** | Remover dependencia |
| 34 | Stubs desativados `sync_legado_to_sqlite` / `sync_sqlite_to_legado` | `home/management/commands/sync_*.py:4-10` | **baixa** | Remover (so levantam `CommandError`) |
| 35 | Assets `Gaz Profile.gif` / `Banner Gaz.png` untracked em `docs/agentes/` | `docs/agentes/` | **baixa** | Ignorar (~1.9 MB) |
| 36 | Backups `.db.*`/`.sqlite3` na raiz (ja ignorados) | `bonfas_classes.db*`, `magias_backup_*.sqlite3` | **baixa** | Higiene de disco: mover para `backups/` |
| 37 | `console.log` de depuracao no editor de mapa | `home/templates/home/pages/mapa.html:1527,1539,1555,2152,2156` | **baixa** | Remover os 5 logs |
| 38 | `print`/`import sys` inline no `discord_callback` (vaza body OAuth no stderr) | `home/views.py:1164,1179` | **baixa** | Trocar por `logging` |
| 39 | `print` engolindo excecao em `DataIndex.build` | `home/tag_engine/validator.py:494` | **baixa** | Trocar por `logging` |
| 40 | `BOT_POSTGRES_TABLES['store']` default nao bate com `db_table` do modelo | `bonfire/settings.py:247` | **baixa** | Corrigir/remover chave `store` (cosmetico, sem bug) |
| 41 | `_pc_display` etc. — one-shots CSV magicos/bestiario a arquivar | `home/management/commands/refinar_itens_magicos_csv.py`, `importar_bestiario_csv.py` | **baixa** | Manter enquanto o par depender; arquivar o resto |

---

## Detalhes por dimensao

### 1. Seguranca e configuracao (`bonfire/settings.py`)

O defeito-raiz e o **default `DEBUG=True`** (`settings.py:63`). `_env_bool('DJANGO_DEBUG', True)` retorna `True` quando a env var esta ausente, entao um deploy que esqueca de setar `DJANGO_DEBUG=false` sobe em producao com DEBUG ligado. Isso cascateia em tres achados dependentes:

- **ALLOWED_HOSTS -> `['*']`** (`70-71`): aceita qualquer `Host` header (host-header/cache poisoning).
- **Cookies nunca `Secure`** (`217-218`): `(not DEBUG) and _env_bool(...)` -> com DEBUG=True, `sessionid`/`csrftoken` trafegam sem flag Secure mesmo sob HTTPS.
- Tracebacks e variaveis expostos ao usuario final.

Corrigir o default de DEBUG para `False` neutraliza os tres de uma vez.

Segredos com **fallback hardcoded em arquivo git-tracked** (violam a higiene do resto do `settings.py`, que le tudo de `os.environ` sem default secreto):

- **`SECRET_KEY`** (`57-60`): fallback `django-insecure-...` publico no historico. Sem env de prod, permite forjar `sessionid` e tokens de reset de senha.
- **`SERVER_LOGS_PASSWORD_HASH`** (`275`): hash `pbkdf2_sha256` publico -> plaintext brute-forcavel offline. E o gate do console que da RCE (ver `admin.py:285`).

**RCE por design** (`home/admin.py:285`): `server_logs_view` autentica contra o hash acima e libera `_run_admin_console_command` -> `subprocess.run(command, shell=True)`. A view esta atras de `admin.site.admin_view` (exige sessao staff), entao sao dois fatores; mas o hash publico derrota a premissa de "senha secreta" e o vetor final e execucao de shell arbitraria no servidor (insider/staff comprometido + hash quebravel).

**`CSRF_TRUSTED_ORIGINS`** (`203-210`): default inclui `https://*.trycloudflare.com` (namespace de tuneis Cloudflare de qualquer pessoa) e um subdominio de dev especifico. Nao deveria ser default em codigo de producao.

Positivos registrados: `asaas_webhook` e fail-closed correto (`views.py:8230`, rejeita token vazio, `@require_POST`); `.env`/`*.sqlite3`/`*.db*` estao gitignored e nenhum `.env` e rastreado; credenciais reais (Discord/Asaas/Email/Postgres/Docs) vem de `os.environ` sem fallback.

### 2. Disponibilidade em producao

- **`/media/` da 404 em prod** (`bonfire/urls.py:12-13`): a rota de media so e adicionada sob `DEBUG=True`. WhiteNoise cobre apenas `STATIC_ROOT`, nao `MEDIA_ROOT`. Uploads de usuario (retratos, banners) quebram a menos que nginx/Cloudflare sirva `/media/` por fora. Bug funcional, nao vuln.

### 3. Higiene de versionamento (arquivos untracked / commitados por engano)

Nenhum destes esta coberto pelo `.gitignore` atual; um `git add .` os captura:

- **`media/`** (~6.97 MB, 5 arquivos): uploads reais de usuario (`character_uploads/`, `profile_uploads/`) = PII binaria. Adicionar `media/` ao `.gitignore`.
- **`backup_sqlite.json`** (~10.5 MB) e **`conteudo.json`** na raiz (~9.9 MB): dumps avulsos do fluxo `dump_conteudo`/`loaddata`. O fixture legitimo `home/fixtures/conteudo.json` e um arquivo distinto e continua rastreado normalmente.
- **`qc`, `query`, `start`** (19 bytes cada, ja **commitados**): saida de comando redirecionada por engano (`postgresql-x64-16`). `git rm` nos tres. Atencao: `start_server.bat`/`start_server_silent.bat` sao scripts legitimos separados — nao tocar.
- **Assets em `docs/agentes/`**: `SKARNER IMAGEM.png` (1.8 MB), `SKARNER TOKEN.png` (1.6 MB), `Gaz Profile.gif` (970 KB), `Banner Gaz.png` (897 KB) — ~5.2 MB de imagens de referencia sem valor de codigo.

Ja ignorados corretamente (apenas higiene de disco, sem risco de commit): `bonfas_classes.db*`, `magias_backup_20260623.sqlite3` (regras `*.db`/`*.db.*`/`*.sqlite3`). `scratch/`, `.env`, `db.sqlite3`, `AI_CONTEXT_DO_NOT_COMMIT.md` confirmados ignorados.

### 4. Codigo morto e orfaos

- **Modulo `google_docs_import.py`** (`1-289`): 100% morto. `import_google_doc()` so referenciado dentro do proprio modulo; nenhum outro `.py` importa dele; nenhuma rota. Remover inteiro (leva junto os imports mortos `os`/`json`).
- **Ramo adaptador legado em `views.py`**: `_legado_classes_view` (`1275`), `_legado_classe_detail_view` (`1622`), `_legado_racas_view` (`2002`), `_legado_raca_detail_view` (`2019`) — todas definidas e nunca chamadas (os dispatchers delegam hardcoded para as variantes `_postgres_*`). Arrastam os mappers `_legado_subclasse/_habilidade/_recurso/_linhagem/_traco` (`459` etc.) **e tambem** `_legado_classe`/`_legado_raca`, cujos unicos call-sites estao dentro das quatro views mortas. Preservar `_legado_docs`/`_legado_collection`/`_legado_upsert_site_document` (vivos: mapa/regioes/jornal).
- **Templates orfaos** `classes.html` e `racas.html` (`:1`): paginas completas (`extends base.html`) que ninguem renderiza/inclui. Consomem `{{ classes }}`/`{{ racas }}`, mas as views fornecem `all_classes`/`all_racas` — contexto descasado. Sobra do commit 3cfb483.
- **Modelo `TbPersonagemPersonalidade`** (`models.py:1363-1370`): `managed=True`, tabela sincronizada, mas zero acesso via ORM ou `related_name='personalidade'`. So aparece na definicao, na migracao 0011 e como string na lista de ordenacao de `deploy_sync.py:32`. Schema morto.
- **CSS orfaos**: `index.css`, `legado_collection_detail.css`, `legado_document_form.css` (`home/static/css/pages/`) — sem `<link>`/`{% static %}`; ja listados como orfaos a deletar em `docs/agentes/arquitetura_personalizacao_perfil.md:141`. `base.html` so linka `base.css` estaticamente, sem loader por convencao.
- **Imagem orfa** `pena_branca.png`: `markdown.js:566,568` so usa `pena_preta.png`.
- **Stubs desativados** `sync_legado_to_sqlite.py` / `sync_sqlite_to_legado.py` (`4-10`): `handle` sempre levanta `CommandError`.
- **`gunicorn==21.2.0`** (`requirements.txt:2`): nunca importado; todos os scripts de deploy usam `waitress` (`start_server.bat:73`, `start_server_silent.bat:31`, `scripts/run_production.ps1:29`); nao ha Procfile/Dockerfile. Alem disso gunicorn nem roda no Windows.
- **Imports mortos**: `views.py:16` (`DjangoJSONEncoder`), `views.py:27` (so `escape`; `format_html`/`format_html_join` seguem vivos), `admin.py:2` (`math`), `admin.py:8` (`urlencode`), `admin.py:56` (so `validate_json_no_sql_danger`; `validate_no_sql_danger` e usado).

### 5. Management commands — one-shots que quebram vs. permanentes

**Quebram ao re-executar** (leem colunas removidas pela migracao 0043 de `TbItemMundano`: `dano`, `propriedades`, `maestria`, `ca`, `ca_base`, `ca_limite_des`, `forca_minima`, `furtividade_desvantagem`, `tipo_equip`):

- **`taggear_itens.py`** (`251-294`, `mundane_tags`): `--tipo` default e `todos`, entao o ramo mundano roda por padrao; qualquer arma/armadura no banco dispara `AttributeError` mesmo em preview. Ramo magico intacto. **Alta** porque nao roda em request de prod, mas o comando esta quebrado.
- **`refinar_itens_mundanos_csv.py`** (`569-688`): quebra ja na fase de leitura (sem `--apply`), pois `build_local_item_block(obj)` roda no loop de coleta. O CSV existe, entao nao ha short-circuit. **Alta**.

**Bug latente / higiene**: `importar_livros.py` (`23-27`) mantem as colunas mortas na allowlist `PLANO['mundano']`; so falha se o JSON de entrada trouxer uma dessas chaves, e o `except` (`91`) engole e descarta a entrada silenciosamente. Podar a allowlist. **Media** (degradacao controlada).

**Permanentes / seguros (manter)** — nenhum toca colunas removidas, todos usam campos vivos:

- Deploy: `dump_conteudo.py`, `sync_conteudo.py` (nucleo do fluxo de deploy por PK/slug).
- Backup/restore: `make_backup.py`, `restore_backup.py`, `restore_ref_backup.py`, `restore_full_backup_local.py`, `export_restore_patch.py` — serializam/filtram por modelo; deserializer do Django ignora campos desconhecidos, entao backups antigos com colunas removidas nao quebram o restore.
- Qualidade/operacional: `validate_tags.py` (tag engine), `ensure_admin_user.py`, `cobrar_mestre_ouro.py` (cron MM), `simular_webhook_asaas.py` (teste), `dedupe_regions.py`, `audit_content_duplicates.py` (read-only).
- Bestiario/limpeza: `importar_bestiario_csv.py`, `gerar_tags_bestiario.py`, `limpar_residuos_banco.py`, `remover_fontes_conteudo.py` — campos vivos de `TbBestiario`. `limpar_residuos_banco` importa helpers de `importar_bestiario_csv`, entao o par deve ser mantido junto.
- `refinar_itens_magicos_csv.py`: nao quebra por schema (`TbItemMagico` intacto); depende de CSV em `scratch/` (nao versionado). One-shot/higiene.

### 6. Migracoes

- **Cadeia linear e integra** (`0001-0046`): verificado empiricamente via `MigrationLoader.build_graph()` — unico leaf node `0046`, `detect_conflicts()` vazio, zero forks, `makemigrations --check` reporta "No changes detected". Nao e necessario `--merge`.
- **Candidata a squash**: 46 migracoes com varios pares add/backfill/remove (`0041->0042->0043->0044` refactor de CA; `0037/0038/0039` remocao de source/fonte; `0006/0007` spells). Sem urgencia; acelera testes/CI. **Atencao**: ha 7 data-migrations com `RunPython` (`0002, 0006, 0007, 0034, 0035, 0042, 0044`) que exigem revisao manual pos-squash.
- **Regra de catalogo em migracao**: `0035_tbantecedente_background_grants` injeta a tag hardcoded `background-grants{...}` em todos os antecedentes. Idempotente e funcional hoje, mas acopla conteudo de catalogo ao schema — candidata a seed/management command.
- **Ponto-de-nao-retorno**: `0042` e `0044` tem `reverse=pass`. Como `0043` remove definitivamente as colunas de snapshot de CA (`ca_base`/`ca_limite_des`/`tipo_equip` em `TbPersonagemItem`), um downgrade abaixo de `0041` perde o snapshot de CA irrecuperavelmente. Inofensivo em forward; documentar.
- **Setup/informativas**: `0002` (`DROP TABLE rpg_items` + reset de sequences, no-op em SQLite), `0007` (reverse deixa a tabela `spells` orfa; `TbMagia` ainda existe). Sem defeito.

### 7. Logging e duplicacao

- **`views.py:6063-6065`** (`wiki_batch_save_map`, except): grava traceback em `batch_save_error.log` com `open(...,'w')` (sobrescreve a cada erro) + `print` para stdout, em vez do `logging` que o projeto ja usa (`signals.py`). **Media** (efeito colateral em prod + perda de logs).
- **`views.py:8350,8393,8432`**: gate `if not request.user.is_superuser: return JsonResponse({'error':'Acesso negado...'}, 403)` copiado verbatim em `wiki_add_layer`/`wiki_edit_layer`/`wiki_delete_layer`. Extrair decorator/helper (risco de divergencia futura). **Media**.
- **`character_engine.py:1730`**: divisao PO/PP/PC inline reimplementa a regra ja em `views.py:_pc_display` (`2894-2906`). Modulos independentes (sem import), entao e duplicacao real da regra numerica — porem formatos de saida diferem (dict vs string), so compartilhariam o helper de aritmetica. **Media/baixa**.
- **`views.py:1164,1179`** (`discord_callback`): dois `print(..., file=sys.stderr)` com `import sys` inline duplicado; o body do `HTTPError` OAuth e truncado e impresso no stderr (vaza detalhe de resposta nos logs do servidor). **Baixa**.
- **`tag_engine/validator.py:494`**: `print(f'  [DataIndex] aviso: {exc}')` engole excecao de modelo ausente; `DataIndex` roda tambem no request path -> deveria ir para `logging`. **Baixa**.
- **`mapa.html:1527,1539,1555,2152,2156`**: 5 `console.log` de depuracao no editor de mapa em producao. **Baixa**.

### 8. Inconsistencia cosmetica

- **`settings.py:247`**: `BOT_POSTGRES_TABLES['store']` default `'discord_bot_store'` nao bate com o `db_table='store_keyvalue'` do modelo `BotKeyValueStore` (`models.py:1005`). A chave `store` nunca e consumida (so `spells`/`backgrounds`/`bestiary`/`organizations`), entao sem bug de runtime — o ORM usa o `db_table` do modelo. Discrepancia confusa a corrigir/remover. **Baixa**.

---

## Quick wins (baixo esforco, alto valor)

1. **`.gitignore`**: adicionar `media/`, `backup_sqlite.json` e `/conteudo.json` (raiz) — remove risco de commitar ~27 MB, incluindo **PII de usuario**. Um so commit.
2. **`git rm qc query start`**: apagar tres arquivos scratch de 19 bytes ja versionados.
3. **`DEBUG` default -> `False`** (`settings.py:63`): uma linha que neutraliza quatro achados (DEBUG + ALLOWED_HOSTS `['*']` + cookies inseguros + exposicao de tracebacks).
4. **Deletar orfaos**: `google_docs_import.py`, `classes.html`, `racas.html`, os 3 CSS (`index.css`, `legado_collection_detail.css`, `legado_document_form.css`), `pena_branca.png`, e os stubs `sync_legado_to_sqlite.py`/`sync_sqlite_to_legado.py`.
5. **Remover imports mortos**: `views.py:16,27`, `admin.py:2,8,56`; e `gunicorn` do `requirements.txt:2`.
6. **Limpar `console.log`** do `mapa.html` (5 linhas) e o `parchment-texture.jpg` faltante do `jornal_list.html:7`.
