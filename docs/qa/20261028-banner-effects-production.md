# Efeitos de banner: reclassificacao aplicada em producao

Executado depois de o PO confirmar `/site update`. Quatro pacotes `efeito-*`
responderam200 com type efeito e scope ambos. Acao administrativa nova presente.

## Protecao anterior

Backup completo salvo pelo admin em
`[local-path]`, JSON valido,
27.823.024 bytes, SHA256
`2f6e95d0ceb7e4f811e36812588de63ce677aa5fd010831ea0908d6683762482`.
Arquivo contem dados privados: nao versionar nem compartilhar como evidencia.
A leitura local para verificacao foi limitada aos quatro cosmeticos e seus
28 registros de inventario, sem dump de usuarios/autenticacao no relatorio.

## Operacao

Acao generica de reclassificacao, somente PKs54/55/56/61; destino efeito,
limpeza da classe antiga selecionada e confirmacao do lote pelo admin.

| PK preservada | Slug anterior | Slug atual |
| --- | --- | --- |
|54|tema-lua-vermelha|efeito-lua-vermelha|
|55|tema-lua-negra|efeito-lua-negra|
|56|tema-lua-cristal|efeito-lua-cristal|
|61|tema-vigilia-das-lanternas|efeito-vigilia-das-lanternas|

Retorno: **4 reclassificados, 1 selecao movida, 0 conflitos**.
Catalogo permanece57; os outros53 registros, textos e links/PKs nao mudaram.
Nenhum novo cosmetico/inventario ou oferta foi criado. Origem staff mantida.

## Conferencia real

- Busca `efeito-lua`: 21 inventarios; `efeito-vigilia`: 7 inventarios.
- Os28 IDs sao exatamente os mesmos do backup, sem repetir concessoes.
- Gaz/editor: nenhum desses itens permanece no seletor Tema. Os4 aparecem
  habilitados no seletor Efeito. Tema bonfire e efeito lua-vermelha, migrados
  pela operacao; nao houve POST extra de salvamento do perfil durante QA.
- Gaz/publico: banner proprio presente no nivel0; pacote Lua Vermelha overlay
  no nivel1, sete imagens carregadas. Banner e composicao visiveis juntos.
- Aparencia vista em navegador real; nao e somente evidencia do preview local.

Restricao continua por inventario dos sete admins anteriores. Nao foi criada
uma regra dinamica de cargo. Retirada de cargo deve incluir revogacao de QA.
Os manifestos tema legados ficam preservados para compatibilidade de arquivos,
mas nao ha mais registros dessas quatro composicoes na categoria Tema.
