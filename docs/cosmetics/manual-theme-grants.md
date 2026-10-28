# Temas das tres luas: concessao manual por administrador

Decisao do PO: temas Lua Vermelha, Lua Negra e Lua de Cristal sao liberados
individualmente por admin, sem compra, resgate publico ou desbloqueio automatico.
Usar o inventario existente, nao criar condicionais por lua nem migration de
concessao. Molduras e Halloween nao ganham nova politica por inferencia.

## Publicar o catalogo uma vez

Configuracao desejada dos tres temas esta em `catalog-draft.json`:
origem `staff`, ativo `true`, preco nulo, requer_plano vazio, escopo `ambos`.
Esse arquivo continua sendo configuracao editorial, NAO fixture de restore.
`activate_in_production: false` significa que este commit nao escreve no banco.

No admin, abrir `/admin/home/tbcosmetico/`, localizar pelos slugs
`tema-lua-vermelha`, `tema-lua-negra`, `tema-lua-cristal`. Editar linhas existentes,
preservando PKs/inventarios; se ausentes, cadastrar usando os dados do arquivo.
Nao criar oferta comercial nem conquista automatica para esses temas.
Ativo torna o tema utilizavel por quem o recebeu, nao livre para todos.

## Liberar para um jogador

1. Abrir `/admin/home/tbusuariocosmetico/add/` como admin com permissao de
   adicionar cosmeticos de usuarios (superuser ja possui).
2. Selecionar o usuario e o tema desejado no autocomplete.
3. Preencher origem `staff`, deixar `suspenso_em` vazio e salvar.
4. O jogador passa a poder escolher o tema na Aparencia do perfil/ficha.
   A concessao nao troca automaticamente o tema equipado.

Nao adicionar permissao administrativa ao jogador. Cada registro libera UM
tema para UMA conta; para os tres temas, tres registros. Duplicatas sao
recusadas pela restricao `(user, cosmetico)`. O admin registra a adicao no
historico administrativo padrao do Django, com ator e objeto.

Se ja existir registro suspenso, revisa-lo explicitamente em
`/admin/home/tbusuariocosmetico/`; nao criar duplicata nem reativar em lote.
Para revogar uma concessao exclusivamente manual, preencher `suspenso_em`.
Nao desativar o catalogo inteiro para revogar apenas um jogador.

## Estado desta entrega

Fluxo e permissoes ja existiam em `home/admin.py`, `home/models.py` e
`home/cosmetics.py`. Nenhum motor novo, arte ou regra de personagem alterado.
Configuracao e testes locais, sem escrita em PostgreSQL ou producao.
Depois de publicar os registros no catalogo, nao e necessario deploy por
concessao: o admin grava o inventario e o motor consulta o direito existente.
