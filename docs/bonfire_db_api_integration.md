# Acesso estruturado do Jarvis ao Bonfire

1. No admin do Bonfire, um superuser abre **Chaves de API**, cria uma chave com `read` e, somente se autorizado para as tarefas previstas, `write` e/ou `publish`. Copie o segredo exibido uma vez. O banco PostgreSQL continua acessível apenas pelo servidor.
2. Em **Integrações > Banco Bonfire por API** no Jarvis local, informe a origem HTTPS do site e a chave. O Jarvis verifica `GET /api/db/v1/session/` antes de salvar. A resposta contém os escopos efetivos e a expiração, sem segredo ou dados de jogadores. A chave fica protegida pelo DPAPI da conta Windows no armazenamento local já usado por conectores.
3. **Testar conexão e escopos** consulta novamente a sessão; **Desconectar** apaga a credencial local. Revogar ou rotacionar no admin invalida a chave antiga no servidor. A chave nunca deve entrar em prompts, logs, URL ou Git.

A conexão não autoriza alterações por si só. Consultas e mutações usam as rotas estruturadas de `api/db/v1/` e seus escopos, preflight, versão, idempotência e auditoria. Publicação de revisão permanece uma operação explícita e separada. Implante código e migrações antes de criar a chave; não use esta interface como substituto de deploy, backup ou migração de schema.
