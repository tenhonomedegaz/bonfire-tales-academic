# Guia operacional da API geral do Bonfire

## Historico das fichas do bot

A entrega local adiciona operacoes administrativas de consulta, previa e
confirmacao de historico, reutilizando a chave existente. Contrato, limites e
instalacao: [importador de fichas do bot](character_log_import.md). Ainda nao
presumir que essas rotas estao presentes na producao antes de instalar o lote.

## Atualizacao: catalogos e comparacao por slug

Esta entrega adiciona GET/POST/PATCH de `talento`, `magia`, `bestiario`, `item_mundano` e `item_magico`, com descricoes e tags completas, mantendo PKs imutaveis, escopos, versao e idempotencia. A chave existente pode ser reutilizada apos instalar o codigo; nao e necessario rotaciona-la. `schema/` passa a listar os campos/choices/referencias. A nova operacao `catalog-upsert-preview` compara lotes por slug sem gravar conteudo. Procedimento completo e exemplos: [API de catalogos](catalog_api.md). O manifesto de 31 epicos em `docs/integracao/talentos-epicos-api-plan.json` e desejado/nao aplicado, nao uma confirmacao da producao.

Este é o procedimento único para operar a API restrita de conteúdo e revisões de classe. Ela não oferece SQL, DDL, shell, dumps, contas ou chaves por token. As rotas da API são registradas em `bonfire/urls.py`; `home/urls.py` não as registra.

Código a instalar: [BonfireSite, branch `dev`](https://github.com/bonfiretales-dev/BonfireSite/tree/dev), a partir de `cae6c85` e com este guia atualizado; [JARVIS-Project, branch `dev`](https://github.com/tenhonomedegaz/JARVIS-Project/tree/dev), commit `4ba93531c73c4b6152209ed3344e2447b7126602`. O servidor usa apenas o commit do Bonfire; o painel local usa o commit do Jarvis. Confira o hash implantado de cada repositório antes de gerar a chave.

## Implantação

No servidor, com o código desta versão instalado e o ambiente virtual ativo, execute:

```powershell
python manage.py migrate --plan
python manage.py migrate
python manage.py showmigrations home
```

Confirme que `0122_managed_api_keys_and_db_access`, `0123_class_publication` e `0124_character_class_ruleset` aparecem aplicadas. A 0122 cria chaves, auditoria e idempotência; a 0123 cria `home_class_publication` e `home_class_publication_log`; a 0124 fixa o ruleset na relação de classe da ficha sem converter fichas antigas. Reinicie a aplicação depois de migrar.

Crie um superusuário somente se não houver um:

```powershell
python manage.py createsuperuser
```

## HTTPS e backup

Toda chamada `/api/db/v1/` é recusada se Django não enxergar HTTPS (`400 https_required`). Publique atrás de TLS e encaminhe corretamente o esquema HTTPS ao Django.

No deploy com **Cloudflare Tunnel + Waitress**, use os scripts `start_server.bat` ou `start_server_silent.bat` desta versão: eles escutam somente em `127.0.0.1:8000` e o Waitress aceita `X-Forwarded-Proto` apenas do proxy local. A rota do túnel deve apontar para `http://127.0.0.1:8000`. Reinicie o processo Waitress após atualizar os scripts; alterar apenas o arquivo sem reiniciar não muda o processo em execução. Não publique a porta 8000 nem aceite esse cabeçalho de clientes diretos. Nesse arranjo, `DJANGO_USE_X_FORWARDED_PROTO` não precisa ser ativado: o Waitress entrega `wsgi.url_scheme=https` ao Django. Se houver outro proxy, só configure `DJANGO_USE_X_FORWARDED_PROTO=true` depois de confirmar que ele remove o cabeçalho enviado pelo cliente e define o valor correto.

Para diagnosticar sem enviar a chave, faça um GET **sem Authorization** em `https://bonfiretales.com.br/api/db/v1/session/`: `401 unauthorized` mostra que o teste passou pela verificação HTTPS e chegou à autenticação; `400 https_required` indica que o esquema ainda não chegou ao Django. Esse teste não valida a chave nem os escopos. Depois que retornar `401`, use **Testar conexão e escopos** em Integrações com a chave guardada localmente; confira também `schema/`. Não cole a chave em chat, URL ou log.

Em produção, configure ao menos:

```text
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=bonfire.exemplo.br
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECRET_KEY=<segredo-de-producao>
```

Use o hostname real em `DJANGO_ALLOWED_HOSTS`. HSTS é configurável por `DJANGO_SECURE_HSTS_SECONDS` e `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`, mas não há valor obrigatório implementado.

Para publicar uma classe, configure antes uma pasta absoluta já existente, fora da árvore servida do projeto e restrita à conta do serviço:

```text
CONTENT_MAINTENANCE_BACKUP_DIR=D:\backups\bonfire
```

`pg_dump` e `pg_restore` precisam estar no `PATH`, ou devem ser definidos em `CONTENT_MAINTENANCE_PG_DUMP` e `CONTENT_MAINTENANCE_PG_RESTORE`. A publicação só aceita PostgreSQL local primário: host loopback/`localhost`, banco e schema `public` esperados e sem réplica. Antes de alterar o vínculo, ela cria dump customizado e valida o índice com `pg_restore --list`. Falha de backup interrompe a publicação. A API não implementa restauração automática, retenção, envio externo ou agendamento; preserve o dump e teste a restauração em ambiente isolado.

## Console de chaves (superuser)

Entre como superuser em `https://<host>/admin/` e abra `https://<host>/admin/api-keys/manage/` (há link na lista administrativa de chaves). O console e os JSONs administrativos exigem sessão de superuser; seus POSTs usam CSRF do Django.

Crie uma chave com escopos mínimos e expiração quando possível. O `secret` de criação ou rotação aparece **uma única vez**; o banco guarda apenas o hash. Copie-o imediatamente para o cofre de segredos. Não o registre em Git, `.env` versionado, prompts, tickets ou logs.

| Método | URL | Resultado |
| --- | --- | --- |
| `GET` | `/admin/api-keys/` | Lista metadados, sem segredo. |
| `POST` | `/admin/api-keys/` | Cria; corpo: `{"name":"Jarvis","scopes":["read"],"expires_at":"2026-12-31T23:59:59-03:00"}`. A expiração pode ser omitida. |
| `POST` | `/admin/api-keys/<uuid>/rotate/` | Cria segredo novo e revoga a chave anterior imediatamente. |
| `POST` | `/admin/api-keys/<uuid>/revoke/` | Revoga a chave; repetir é seguro. |

Os únicos escopos são `read`, `write` e `publish`. Em incidente ou perda de segredo, revogue primeiro, crie ou rotacione a substituta, atualize o cofre e depois o consumidor.

## Uso da API

O Jarvis envia `Authorization: Bearer` por HTTPS internamente. O segredo fica no cofre local e nao precisa ser copiado para comandos, prompts ou historico. Use **Testar conexao e escopos** em Integracoes para consultar `session/`; o agente consulta `schema/` pela ferramenta protegida.

`schema/` é a fonte de verdade para modelos, campos e operações expostos pela versão implantada. `session/` confirma conexão, escopos e expiração. Os modelos sao `regra`, `idioma`, `condicao`, `raca`, `linhagem`, `opcao_jogo`, `acesso_opcao`, `talento`, `magia`, `bestiario`, `item_mundano` e `item_magico`; a allowlist não inclui usuários, chaves, auditoria, revisões, rulesets ou personagens. `opcao_jogo` e `acesso_opcao` expõem somente consulta estruturada; seus campos aparecem com `writable: false` no schema. A publicação de opções e vínculos de acesso requer um fluxo especializado ou decisão de contrato própria, pois alterar esses vínculos afeta a elegibilidade de personagens.

| Método | URL | Escopo | Regras |
| --- | --- | --- | --- |
| `GET` | `/api/db/v1/<modelo>/` | `read` | `filter[campo]` exato, `fields`, `ordering`, `page` e `page_size`, somente conforme schema. |
| `POST` | `/api/db/v1/<modelo>/` | `write` | JSON de campos graváveis e `Idempotency-Key`. |
| `GET` | `/api/db/v1/<modelo>/<pk>/` | `read` | Retorna item e `version`; a versão também está no `ETag`. |
| `PATCH` | `/api/db/v1/<modelo>/<pk>/` | `write` | JSON parcial, `Idempotency-Key` e `If-Match` com a versão atual. |
| `POST` | `/api/db/v1/operations/<nome>/` | varia | JSON, `Idempotency-Key` e `base_version` quando exigido. |

Limites: corpo JSON até 64 KiB, no máximo oito filtros, `page_size` de 1 a 100 e 60 requisições por minuto por chave. Excesso retorna `429` e `Retry-After: 60`; respostas usam `Cache-Control: no-store`.

### Preflight, idempotência e auditoria

Antes de escrever, leia ou faça prévia. Para `PATCH`, copie a `version` para `If-Match`; diante de `412 version_conflict`, releia, reconcilie e tente com nova chave de idempotência.

Cada `POST` e `PATCH` da API de conteúdo, além de cada operação, exige `Idempotency-Key` não vazia de até 200 caracteres. Para a mesma chave de API, repetir método, URL e corpo idênticos devolve a resposta armazenada; reutilizá-la com requisição diferente devolve `409 idempotency_conflict`. Gere uma chave para cada intenção, inclusive para cada preview e apply.

Chamadas autenticadas e ações de chave geram `home_db_access_audit` com ação, modelo/operação, objeto quando houver, campos e status. A auditoria administrativa não registra o usuário nela; a chave preserva `created_by`. Não há consulta de auditoria por token: use Django admin ou banco por procedimento administrativo autorizado.

## Revisão e publicação de classes

As operações são `class-revision-preview` (`read`), `class-revision` (`write`), `class-publication-preview` (`read`) e `class-publication` (`publish`), sempre em:

```text
POST /api/db/v1/operations/<nome>/
Authorization: Bearer <segredo>
Content-Type: application/json
Idempotency-Key: <chave-nova-por-chamada>
```

`class-revision-preview` valida e calcula checksums sem persistir. `class-revision` cria ruleset imutável, retorna `activated: false` e não altera linhas vivas, fichas ou publicação. Seu corpo aceita apenas `base_version`, `class_id`, `presentation_source` (`catalog`) e `changes`. Cada mudança usa `home.tbclasse`, `home.tbsubclasse`, `home.tbclassehabilidade` ou `home.tbrecursoclasse`; a ação é `add`, `update` ou `remove`. `add` copia linha existente do catálogo da classe, `update` aceita campos permitidos e `remove` só omite a linha da nova revisão.

`class-publication-preview` confere classe, ruleset de destino, contagens e vínculo atual sem escrever. `class-publication` exige `publish`, lock transacional e backup válido; muda o vínculo comum e registra `home_class_publication_log`. Se o ruleset já estiver publicado, não cria backup ou log. Fichas já fixadas preservam seus vínculos.

Para o Cacador v2, o arquivo versionado `home/content_packages/hunter_v2_class_revision.json` e a fonte local a revisar. O agente deve consultar `schema/`, conferir IDs e checksum da revisao de base no destino e executar `class-revision-preview` com o conteudo verificado. Depois, uma proposta `class-revision` aprovada usa o mesmo contrato generico de qualquer classe. O apply cria uma revisao imutavel com `activated: false`; o checksum retornado por ele vira `target_checksum` de uma nova previa de publicacao. A publicacao exige proposta e confirmacao separadas:

```json
{
  "base_version": "unpublished",
  "class_id": 4,
  "target_checksum": "<ruleset_checksum-verificado>"
}
```

Use `unpublished` somente sem vinculo em `home_class_publication`; caso exista, `base_version` deve ser o checksum publicado atual retornado pela previa. Em `409 publication_conflict`, faca nova previa. O exemplo nao confirma que `class_id: 4` ou quaisquer checksums existam no banco alvo: obtenha-os da consulta/preflight no ambiente de destino.

## Jarvis Integracoes e operacao pelo agente

No Jarvis local, abra **Integracoes > Banco Bonfire por API**, informe somente a origem HTTPS (por exemplo `https://bonfiretales.com.br`) e cole a chave no campo de senha. Salve e use **Testar conexao e escopos**. O segredo e protegido pelo DPAPI da conta Windows; o painel mostra escopos e expiracao, nunca retorna a chave. **Desconectar** remove a copia local; revogar no console superuser interrompe chamadas futuras mesmo que o Jarvis continue conectado.

Em uma tarefa no Jarvis, o agente Codex usa as ferramentas `bonfire_schema`, `bonfire_list` e `bonfire_get` para ler modelos permitidos e versoes sem receber a chave. `bonfire_preview` executa preflight de revisao/publicacao. `bonfire_propose_mutation` confere escopo, campos e versao ou previa e registra uma proposta local: **nao escreve no Bonfire**. A ferramenta devolve o payload exato e o resultado do preflight para revisao do usuario. O usuario precisa responder no mesmo chat `confirmo Bonfire <8 primeiros caracteres do ID>`; so entao o Jarvis envia a operacao com a mesma chave de idempotencia. `cancela Bonfire` descarta a proposta. Uma chave com `read` apenas nao pode propor escrita; `publish` e distinto de `write`. O backend valida tudo novamente e audita chamadas. Nao aprove proposta cujo conteudo, classe, campos ou destino nao correspondam a tarefa autorizada.

O MCP e adicionado ao Codex pelo lancador local somente quando a integracao esta conectada e a sessao tem canal de retorno. O perfil temporario por execucao contem caminho e canal, sem segredo, e e removido ao fim. A API nao oferece delete em massa, DDL, SQL ou operacoes em contas/personagens; consultas vivas nao substituem backup recuperavel. O usuario implanta os commits no servidor e gera a chave no console: o Jarvis nao faz deploy, migrate nem acesso direto ao PostgreSQL de producao.

A migracao dos demais consumidores de classe para o vinculo comum de publicacao segue como trabalho DEV separado. Ha compatibilidade legada enquanto uma classe nao possui vinculo publicado; isso nao comprova QA remoto do Cacador.
