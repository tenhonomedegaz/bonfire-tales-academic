# API de catalogos: leitura, edicao e previa

Esta entrega amplia a API existente; nao cria uma segunda API nem exige rotacionar chaves. Depois de instalar o codigo, a mesma chave com `read` consulta os novos modelos e uma chave com `write` edita os campos permitidos. A migration `0161` pertence a categoria geral de talentos epicos, nao a infraestrutura desta ampliacao da API.

## Contrato

Base: `https://bonfiretales.com.br/api/db/v1/`. Sempre HTTPS e `Authorization: Bearer <segredo>`. O console de chaves continua exclusivo de superuser em `/admin/api-keys/manage/`. Para Schmidt/Foundry, preferir chave propria somente de leitura; ela nao deve ser inserida em JavaScript publico.

`GET schema/` informa modelos e campos reais, tipos, escolhas validas, tamanho maximo, permissoes e referencias JSON. `GET session/` confirma a chave e seus escopos sem revelar o segredo.

| Modelo | Conteudo completo relevante | Escrita |
| --- | --- | --- |
| `talento` | descricao, pre_requisito, tags_json, tipo, etiquetas e flags legadas de atributo | POST/PATCH; tipo origem, geral ou epico |
| `magia` | descricao, em_niveis_superiores, tags_json, dados de conjuracao, classes_slugs | POST/PATCH; slugs de classe precisam existir e ser distintos |
| `bestiario` | descricao_markdown, statblock_json, tags_json, CA/PV/ND e vinculos de companheiro | POST/PATCH dos campos editoriais/mecanicos; vinculos de classe/subclasse e comunidade apenas leitura |
| `item_mundano` | descricao_markdown, tags_json, categoria, peso e preco | POST/PATCH; nao existe nome_ingles neste modelo |
| `item_magico` | descricao_markdown, tags_json, preco, loja, raridade e sintonizacao | POST/PATCH; preco decimal serializado como texto exato |

Continuam disponiveis regra, idioma, condicao, raca e linhagem; opcao_jogo e acesso_opcao permanecem apenas leitura. Nao ha acesso a contas, jogadores, personagens, chaves, SQL livre ou DELETE. PKs nao sao gravaveis. O autor do bestiario nao e exposto. Um campo JSON nao implica que contenha a descricao: tags e narrativa devem ser lidas separadamente.

`classes_slugs` e a fonte mecanica do acesso de magias; `classes` permanece texto editorial. A API valida os slugs enviados, mas nao reescreve automaticamente o rotulo. Editar somente `classes` nao substitui a lista mecanica.

## GET e paginacao

```text
GET talento/?filter[tipo]=epico&fields=id_talento,slug,nome,tipo&page_size=100&page=1
GET talento/?filter[slug]=dadiva-do-destino
GET talento/123/
GET bestiario/?fields=id_criatura,slug,nome,tipo,nd&page_size=25&page=1
GET bestiario/123/
GET magia/?filter[nivel]=2&page_size=25&page=1
GET item_magico/?filter[loja]=Joalheria&fields=id_item,slug,nome,loja&page_size=100
```

PKs 123 sao exemplos, nao identidades para sobrescrever. Liste/filtre primeiro e use a PK devolvida pelo servidor. Filtros sao de igualdade e somente nos campos permitidos; nao aceitam lookups ORM arbitrarios. `ordering` aceita um campo permitido, com `-` para descendente. Ate oito filtros e vinte campos explicitamente selecionados; page_size de 1 a 100. Iterar ate atingir `total`; nao presumir que a primeira pagina contem tudo. Para descricoes/statblocks grandes, usar pagina pequena ou buscar detalhes individualmente; nao truncar textos para caber em uma resposta do cliente.

As consultas nao prometem snapshot de toda a base durante paginacao. Para comparar registros editaveis, utilizar a versao do GET de detalhe, nao apenas o resultado de uma listagem.

## POST/PATCH

POST em `<modelo>/` recebe um objeto de campos, nao uma fixture Django. Exige `write` e `Idempotency-Key`. PATCH em `<modelo>/<pk>/` recebe apenas campos alterados e tambem exige `If-Match` com a versao do detalhe. Chaves de idempotencia devem ser novas por alteracao logica; se houver timeout, repetir o mesmo corpo com a mesma chave. Nao repetir mudanca diferente com a mesma chave.

```http
PATCH /api/db/v1/talento/<pk>/
Authorization: Bearer <segredo>
Content-Type: application/json
If-Match: <version-do-GET>
Idempotency-Key: <uuid-da-alteracao>

{"descricao":"**Titulo**\n\nTexto revisado.","tags_json":["speed:+10"]}
```

O exemplo ilustra o contrato, nao autoriza modificar um talento real. Nao substituir a lista de tags por um exemplo de documentacao. Tags devem ser lista de textos e passam pelo validador existente; erros sao rejeitados. Avisos nao significam mecanica implementada nem certificam referencias/eventos de combate. JSONs estruturados devem preservar lista/objeto conforme o campo. Uma correcao de descricao pode preservar tags legadas nao tocadas; nao e preciso reescrever toda a ficha para corrigir um paragrafo.

Conflito de versao retorna 412; versao ausente retorna 428; escopo insuficiente, 403; erro de campo/validacao, 400; conflito de integridade concorrente, 409. Detalhes SQL nao sao expostos. A API mantem auditoria e recibos; repetir uma escrita reconhecida nao duplica a operacao.

Editar catalogo nao migra automaticamente personagens presos a revisoes antigas. Revisao/publicacao de classe continua nas operacoes especializadas existentes. Nao trocar PKs, restaurar banco local sobre producao ou renomear slugs sem conferir referencias.

## Previa generica por slug, sem gravar conteudo

`POST operations/catalog-upsert-preview/`, com escopo `read` e `Idempotency-Key`, aceita:

```json
{
  "model": "talento",
  "items": [
    {"slug": "registro-existente", "descricao": "Texto proposto"},
    {"slug": "registro-novo", "nome": "Nome", "tipo": "epico", "descricao": "Texto", "tags_json": []}
  ]
}
```

Somente modelos editaveis com identidade `slug`. De um a dez registros por chamada, respeitando o corpo maximo de 64 KiB. Slugs repetidos sao rejeitados. Campos/valores recebem a mesma validacao estrutural do CRUD. A resposta informa contagens `create`, `update`, `unchanged`; cada operacao inclui `slug`, PK encontrada na producao, versao anterior e valores antes/depois dos campos divergentes. `content_mutated:false`: nao grava catalogo, mas o envelope comum registra auditoria/idempotencia operacional.

Esta rota nao aplica o lote. Depois da revisao, usar POST para registros ausentes e PATCH para os existentes, com as PKs/versoes devolvidas. Reler se o banco mudar; o preview nao e uma reserva de escrita nem garante que sinais/constraints futuros nao recusem a aplicacao. Nao existe exclusao implicita: registro omitido do lote continua no banco. Nao e merge de backup por PK.

Cada conferencia nova usa uma Idempotency-Key nova. Repetir a mesma chave/corpo retorna a previa anterior armazenada, nao uma nova leitura do estado do banco.

## Pacote preparado dos 31 epicos

`docs/integracao/talentos-epicos-api-plan.json` e um manifesto **desejado, nao aplicado**: sete lotes com ate cinco registros, sem PKs locais. Enviar somente cada objeto de `batches` para a rota de previa, nao o manifesto inteiro. Revisar os resultados antes de qualquer escrita. Ele nao informa quantos registros existem na producao: isso so pode ser determinado depois da implantacao da allowlist e da consulta real.

Os quatro efeitos declarativos sem consumidor continuam descritos no manifesto e fora de tags executaveis. Nao anunciar automacao completa de todos os efeitos apenas porque existem 31 definicoes. O pacote e um retrato dos defaults de carga; nao reaplica-lo sobre edicoes manuais sem comparar os campos e as tags atuais.

## Roteiro de ativacao

1. Atualizar o site pelo `/site update` do bot, que ja faz pull/migrate/collectstatic/restart. Nao e necessario comando extra de servidor para habilitar os novos modelos, nem gerar outra chave.
2. Consultar session/schema com a chave existente; o schema deve conter os cinco catalogos novos e `catalog-upsert-preview`.
3. Ler os talentos por slug e executar as sete previas do manifesto. Registrar criacoes/alteracoes/iguais e conflitos, sem fazer dump de usuarios ou da base inteira.
4. Revisar a diferenca. Efetuar somente as escritas aprovadas com versao/idempotencia e guardar o conteudo anterior em local protegido. A API nao cria automaticamente um pg_dump por PATCH.
5. Reler os registros e verificar a pagina. Codigo instalado, dados publicados e efeitos conferidos sao marcos diferentes.

Limites mantidos: 60 requisicoes por minuto, Retry-After em 429, corpo maximo de 64 KiB. Para o Foundry, combinar o formato/versao de destino depois de extrair a narrativa e o statblock completos. Exportador Excel continua uma entrega separada.

O conector atual do Jarvis ja consulta listas/detalhes e prepara POST/PATCH dos modelos informados pelo schema. Sua lista de operacoes de preview ainda e explicita e precisa incorporar `catalog-upsert-preview` para expor essa nova operacao pelo MCP; clientes HTTP diretos podem utiliza-la apos o deploy. Nao reiniciar o Jarvis so para consultar a API.
