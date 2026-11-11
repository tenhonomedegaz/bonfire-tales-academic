# Relatorio do restore consolidado 20260728_234529

- **Arquivo**: `ref/backups/restore_consolidado_20260728_234529.json` (5061 registros; NAO versionado — politica 20/07)
- **SHA-256**: `f0d3f9dd4340359e934b342b66aa851cc3c48c023fbbd620da39e1432371f4cc`
- **Report**: `ref/backups/restore_consolidado_20260728_234529.report.json`
- **Substitui**: `restore_consolidado_20260728_194351.json` (sha be53e511...) — engloba tudo dele.

## Diff vs 20260728_194351 (3 registros de TbItemMagico)

1. **pk331** `distintivo-da-guarda`: nome "Distintivo da Guarda" -> **"Insígnia da Vigília"** (decisao do PO, 28/07; slug intacto).
2. **pk411/pk818 (Pena de Quaal)**: os SLUGS estavam trocados entre as variantes Leque e Arvore (o conteudo/nome ja tinha sido corrigido na onda anterior). Agora: pk411 = `token-de-pena-de-quaal-leque` (Leque), pk818 = `ficha-de-pena-de-quaal-arvore` (Arvore). Slugs e conteudo finalmente coerentes.

**ATENCAO (efeito colateral esperado do item 2):** o merge upserta TbItemMagico por SLUG preservando o PK da prod. Como os slugs foram trocados entre os dois registros, o conteudo dos dois PKs em prod TROCA de lugar: quem tiver uma das duas Penas de Quaal no inventario vai ver a variante virar a outra (Leque <-> Arvore). E a correcao do erro historico; se algum jogador possuir o item, a staff pode reconceder a variante certa pelo painel.

Tudo o mais e identico ao 20260728_194351: 251 renomes de itens via ponte EN, 91 normalizacoes de loja "Somente via Quest", 29 tags de conjuracao inata com uses/at_will (validate_tags ERROR=0 WARN=0).

## Provas (28/07)

- Suite completa: `manage.py test home --parallel 4` -> **Ran 563 tests / OK** (exit 0).
- `validate_tags`: **ERROR=0 WARN=0 INFO=0**.
- Fixture `home/fixtures/conteudo.json` + manifesto regenerados do dev (5244 registros / 26 modelos); TbCosmetico ja alinhado em pk 23-28 (sem correcao manual).
- Render: editor de perfil com previa viva (200), preview POST com vars de tema (200), perfil publico via partial unico (200).

## Checklist de deploy (PO)

1. `force_update.bat` — traz codigo + migracoes ate **0087** (0086 ledger de missoes + 0087 notas do jogador; so ADD COLUMN).
2. Console do admin: **backup** do banco.
3. Console do admin: **Merge de conteudo** com `restore_consolidado_20260728_234529.json` (upload do disco local).
4. Smoke: ficha de um personagem (carteira PO/PP/PC), vitrine do Mercado (nomes novos), catalogo magico ("Insígnia da Vigília"), editor de perfil (previa viva).
5. Rollback se necessario: `ref/backup_completo_20260722_230533.json` (acao "Restaurar backup").

Memoria (usuarios/personagens/transacoes) nao e tocada pelo merge; mundo/mapa/organizacoes ausentes do fixture = prod vence, como sempre.
