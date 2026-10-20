# Redesign Bonfire: release e reversão

## Estado e referências em 20/10/2026

| Referência | SHA / estado |
| --- | --- |
| Fonte visual fixada | `BonfireSite-redesign@7289711136e340afe5a13ba397ecce978071896d` |
| Base comum com `dev` | `7e4c13b12f93f1e9678a7826b87ee897a0230a8f` |
| Base desta frente S11 | `2368953bebe375c2247724c8c5be08ba771c10d1`, branch `jarvis/parallel-2959a1cf-96d6-4c7f-99fa-fe9bc113c3ff/2` |
| `dev` local observado na preparação | `2a0c65048c93e3625f7726d786ec00db12304202`; confirmar de novo antes de S12 |

S09 foi aceita para prosseguir com S11. O handoff compartilhado está em
[redesign-s09-handoff.md](redesign-s09-handoff.md); a cobertura versionada de
rotas inclui `18b1373` (matriz aprovada), `b27fa4f` (inventário original) e
`789c04b` (limites dinâmicos legados). Isso não substitui o aceite de S10:
suite geral, matriz completa do charbuilder e QA visual/funcional ainda precisam
de resultado consolidado. S11 é o guia; esta revisão não conclui S10, não integra
`dev` e não autoriza S12 ou produção.

## Gates efetivos

| Gate | Estado e evidência exigida | Efeito |
| --- | --- | --- |
| G01-A | Aprovada só a consulta/apresentação existente do mercado. Caravana, estoque novo, `0152_magic_market_caravan` e `0153_fate_deck_server_attunement` da fonte seguem sem aceite. | Manter regras, preços, dados e sintonização atuais. |
| G01-B | Perfil, anúncios, portfólio e vitrine de mesas aprovados somente em DEV isolado. | Não alterar cargo, propriedade de missões ou política do bot; anúncios pagos seguem ilustrativos e moderados. |
| G01-C | Aprovados o resgate de slot por 5.000 MM, o fluxo mínimo de tokens/slot por ficha para novos marcos e a Lenda pública com migration própria, conforme [proposta C](redesign-g01-c-tokens-proposta.md). | Preservar direitos históricos; sem token retroativo, entrega automática de item, conversão de saldo de conta ou publicação de solicitação privada de missão. |
| G01-D | Piloto de temas e economia aprovado apenas em DEV isolado, com inventário e reversão prévios. | Oferta demonstrativa não cobra; preservar recibos, direitos, saldo e posses. |
| G01-E/F | E apenas nas adaptações necessárias aos lotes aprovados; F adiado. | Sem importação de fixtures, regras ou mecânicas. |
| S10 | Aceite consolidado ainda exigido: suite geral, charbuilder, QA e regressões abaixo. | Sem esse aceite, S12 permanece pendente. |
| G00 | Reconciliação da entrega predecessora com `dev`, preservando conteúdo local, ainda exigida antes de S12. | Sem G00, não integrar nem fazer push de S12. |
| G02 | PO ainda precisa autorizar e executar a atualização de produção. | Só depois ocorre smoke S13 no site/API; push em `dev` não comprova deploy. |

As decisões vigentes e o histórico da proposta estão em
[redesign-g01-proposta.md](redesign-g01-proposta.md). Cada sublote mantém o próprio
limite de autorização. Os números 0152–0160 **locais** não são as migrations
0152–0160 da fonte: localmente 0152–0154 e 0156 pertencem a B, 0155 e
0158–0159 a D, 0157 reúne B/D sem operação de dados e 0160 cria a Lenda de C.
Não aplicar a cadeia da fonte, usar `--fake` ou editar migration já aplicada.

## Sequência DEV até S12

1. Registrar os SHAs de origem e `dev` novamente, branch, `git status --short`,
   diff e sublotes G01 efetivamente incluídos. Concluir G00 antes da integração
   final; não sobrescrever `main` nem tomar o SHA acima como `dev` imutável.
2. Identificar o PostgreSQL **DEV isolado** e conferir integridade de PK/FK,
   `git diff --check`, `py -3 manage.py check`,
   `py -3 manage.py makemigrations --check --dry-run` e
   `py -3 manage.py migrate --plan`. Conferir nomes e dependências reais das
   migrations locais, sem inferir autorização pelo número.
3. Antes de qualquer migration ou operação de dados aprovada, obter backup
   verificável do banco alvo e registrar fora do repositório horário,
   identificador, checksum e procedimento de restauração. Para D, no head
   `0154_redesign_master_portfolio`, exportar o inventário completo com
   `preview_redesign_d --expected-home-head 0154_redesign_master_portfolio
   --output <json-absoluto-fora-do-repositorio>` e guardar seu SHA-256. A prévia
   restrita `preview_redesign_d_rewards` serve apenas à reconciliação de
   recompensas, nunca ao rollback completo do piloto.
4. Conferir `pg_restore -l` **e restaurar integralmente** o arquivo em banco
   temporário, com verificação de migration, PKs e FKs. O ensaio já registrado
   em `ea4dbf7` recuperou o arquivo do banco isolado: `pg_dump` 18 havia
   incluído `SET transaction_timeout = 0;`, rejeitado pelo servidor local.
   Gerou-se SQL com `pg_restore --no-owner --no-acl -f restore.sql <arquivo>`,
   removeu-se somente essa diretiva da **cópia** e executou-se
   `psql -v ON_ERROR_STOP=1` no banco temporário. Preservar o arquivo original;
   repetir a adaptação somente se o mesmo erro ocorrer no destino. Esse ensaio
   não é prova de backup atual do DEV nem de restauração em produção.
5. Aplicar apenas migrations e reconciliações aprovadas no DEV identificado,
   em ordem verificada, com inventário e plano de reversão do lote. Executar
   testes regionais dos comportamentos alterados. Não usar `loaddata` por PK
   para transportar catálogo; para conteúdo aprovado, seguir
   [deploy-sync-conteudo.md](../deploy-sync-conteudo.md) com chaves naturais e
   PKs/FKs existentes preservadas.
6. Em S10, registrar SHA, ambiente, comando, saída/código de retorno e achados
   da suite geral, matriz completa do charbuilder, rotas de S09, login/CSRF,
   permissões e privacidade, pagamentos/Asaas, publicidade e fluxos legados.
   Fazer QA de teclado/foco, formulários admin, mercado, ficha e screenshots
   em 360/390/768/1024/1440 px. Anexar rotas, passos de reprodução e contas
   de teste apenas por referência ao cofre, sem credenciais. Falhas abertas ou
   evidência ausente impedem o aceite de S10.
7. Com S10, S11 e G00 aceitos, revisar o diff final e integrar em `dev` no S12.
   Registrar o SHA publicado e o QA correspondente. Push, deploy e smoke S13
   são marcos distintos; produção depende da ação do PO em G02.

## Reversão por lote

Primeiro isolar escrita/ações do lote afetado e registrar SHA, ambiente,
horário, registros alterados e backup verificado. Preferir novo commit revisado
para restaurar CSS, JS, templates e rotas; preservar histórico e dados para
auditoria. Reversão de schema só após exportar os registros novos, conferir
dependências e PK/FK e ensaiar a recuperação. Nunca fazer rollback cego da
cadeia de migrations.

| Lote | Desativação e recuperação |
| --- | --- |
| A | Retirar apenas a consulta/apresentação introduzida. Caravana, estoque e sintonização da fonte não fazem parte do lote autorizado. Se um futuro aceite incluir a `0153` da fonte, corrigir os três itens por PK/slug com backup; o `backwards` não é seguro após edição manual. |
| B | Retirar rotas de perfil, moderação, portfólio e anúncios; despublicar itens sem apagar revisões ou direitos. Exportar perfis, trabalhos, decisões e anúncios antes de qualquer mudança de schema. Preservar FKs e contratos do bot. |
| C | Suspender novas concessões e pedidos; preservar fatos de tokens/slot por ficha, direitos Esmeralda históricos, transações e ledger do resgate MM. Eventual estorno exige lançamento compensatório auditável, sem apagar débito. A Lenda local `0160_tbfeitolenda` requer exportação de feitos e conferência da FK da ficha antes de reversão de schema. Não importar o backfill da `0157` da fonte. |
| D | Desativar ofertas e rotas. Com o inventário pré-D completo e SHA-256 da mesma conexão, `rollback_redesign_d_pilot --snapshot <json> --sha256 <hash> --confirm G01-D-ROLLBACK-PILOT` fecha ofertas e restaura recompensas em uma transação; arquiva temas sem uso e mantém ativos os adquiridos. Registrar `archived_slugs` e `retained_owned_slugs`. Para resgates MM, decidir por recibo e usar `reverse_redesign_d_mm` como compensação auditável: preservar recibo/débito e restaurar a posse anterior. |
| E | Retirar a exposição das rotas/serviços do lote afetado e restaurar configuração versionada compatível. Conferir autenticação, CSRF, permissões, métodos e checkout; não apagar variáveis do cofre. |
| F | Adiado. Se receber aceite futuro, reverter conteúdo por patch auditado e chave natural, preservando PKs de produção, fichas, missões e transações; nunca `flush` ou fixture por PK. |

Para recompensas de assinatura importadas **depois** do inventário pré-D,
capturar `preview_redesign_d_rewards --output <novo-json-absoluto>` antes de
desativá-las. Seu snapshot restrito e SHA-256 servem apenas a
`reconcile_redesign_d_rewards`; não arquivam o piloto. O `RunPython.noop` da
`0158` **da fonte** também não restaura recompensas. Não confundir essa
migration com `0158_redesign_cosmetic_mm_redemption` local.

Após G02 e a atualização executada pelo PO, S13 deve conferir o SHA servido,
site/API, login, ficha/charbuilder, mercado, anúncios e logs. Registrar seu
resultado separado do push e do deploy.
