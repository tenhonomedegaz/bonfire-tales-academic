# Guia para agente paralelo: livros base, itens, criaturas e regras

## Objetivo

Refinar o catalogo mecanico usando os PDFs em `ref/Livros`, sem trabalhar em classes, racas, talentos ou magias.

Escopo permitido:

- Itens mundanos para `TbItemMundano`.
- Itens magicos para `TbItemMagico`.
- Criaturas para `TbBestiario`.
- Regras de combate e regras opcionais para futura codificacao do VTT.

Fora de escopo:

- Nao importar novas magias.
- Nao alterar classes, subclasses, racas, linhagens, essencias, talentos ou habilidades.
- Nao copiar texto integral dos livros para descricoes. Extraia campos estruturados e resuma prosa.
- Nao gravar direto no banco sem gerar uma etapa revisavel.

## Fontes e precedencia

Use sempre a versao mais nova e mais limpa quando houver duplicidade.

Monstros:

1. `5. MM (2026) - DnD Beyond - Expanded [5.5e].pdf`
2. `2. MM (2024) - DnD Beyond RIP + Latest Feb-2025 [5e] (1).pdf`
3. `3. MM (2024) - Scanned + Alternate Cover + Latest Feb-2025 [5e].pdf`
4. `4. MM (2024) - AI Upscaled + HQ [5e].pdf`
5. `1. MM (2014) - [Remastered + Deluxe][11th Print].pdf`

Itens mundanos e regras de jogador:

1. `2. PHB (2024) - [D&D Beyond RIP].pdf`
2. `1. PHB (2024) - [AI Upscaled+Bookmarked+Hyperlinked].pdf`
3. `4. PHB (2014) - Core Rules (5th Edition).pdf`

Itens magicos, tesouro e regras de mestre:

1. `3. DM's Guide (2024) - 5e (D&D Beyond RIP + Improved).pdf`
2. `2. DM's Guide (2024) - 5e (Transcribed + Hi-Res).pdf`
3. `1. DM's Guide (2014) - 5e.pdf`

Se duas fontes discordarem, mantenha a fonte de maior precedencia e registre a divergencia no manifesto.

## Antiduplicidade

Antes de propor criacao, normalize:

- `slug` canonico em kebab-case a partir do nome em ingles ou nome usado no catalogo atual.
- Nome PT e nome EN, quando existirem.
- Fonte (`PHB24`, `DMG24`, `MM26`, etc.) e pagina/local.
- Tipo principal: item mundano, item magico, criatura, regra.

Agrupe duplicatas por:

- Mesmo slug canonico.
- Mesmo nome normalizado em ingles.
- Mesmo nome traduzido ja existente.
- Statblock quase identico com fonte mais antiga.

Resultado esperado por entrada:

- `action:create` quando nao existir equivalente.
- `action:update` quando refina uma entrada existente.
- `action:skip_duplicate` quando existir versao mais nova/canonica.
- `duplicate_of:<slug>` quando for duplicata.

## Entrega esperada

Nao faca import direto como primeiro passo. Gere arquivos revisaveis em `scratch/import_livros/` ou outro staging ignorado pelo git:

- `manifest.json`: lista de entradas com `tipo`, `slug`, `nome`, `nome_en`, `source`, `page`, `action`, `duplicate_of`, `notes`.
- `itens_mundanos.json`: campos compatíveis com `TbItemMundano`.
- `itens_magicos.json`: campos compatíveis com `TbItemMagico`.
- `criaturas.json`: campos compatíveis com `TbBestiario`.
- `regras_vtt.json`: regras core/opcionais para futura implementacao.

Depois do manifesto revisado, preparar comando/rotina de import idempotente por `slug`.

## Campos principais

`TbItemMundano`:

- `nome`, `slug`, `categoria`, `subcategoria`, `fonte`, `peso`, `preco`
- Armas: `dano`, `propriedades`, `maestria`, `tags_json`
- Armaduras: `ca`, `tipo_equip`, `ca_base`, `ca_limite_des`, `forca_minima`, `furtividade_desvantagem`, `tags_json`
- `descricao_markdown`: resumo curto, nao transcricao longa.

`TbItemMagico`:

- `nome`, `slug`, `raridade`, `requer_sintonizacao`, `slot`, `tipo`, `fonte`
- cargas/usos/consumo devem virar `tags_json` mecanicas, nao logica hardcoded.
- Pocoes e pergaminhos devem ser marcados como consumiveis pelo tipo/slot ou tag existente.

`TbBestiario`:

- `nome`, `slug`, `tipo`, `tamanho`, `nd`, `alinhamento`, `source`
- `ca`, `pv`, `statblock_json`, `tags_json`, `descricao_markdown`
- Preferir `statblock_json` no schema 5etools quando possivel.
- Acoes, bonus actions, reactions, senses, resistencias, imunidades e condicoes devem ficar estruturadas.

`TbRegra` / regras VTT:

- `slug`, `nome`, `nome_en`, `categoria`, `definicao`
- Para VTT, inclua tambem campos de staging: `rule_kind`, `default_enabled`, `toggleable`, `tags_json`, `implementation_notes`.

## Regras de combate e opcionais para VTT

Prioridade inicial:

- Cobertura (`cover-half`, `cover-three-quarters`, `cover-total`): regra core, toggleavel apenas para variantes.
- High ground: regra opcional/mesa, default desativado ate decisao de design.
- Flanco: regra opcional, default desativado.
- Inspiracao para rerolar apos falha: regra opcional, default desativado.

Modele regras opcionais como dados, nao ifs soltos no futuro VTT. Cada regra precisa dizer:

- Quando dispara.
- Quais entradas o VTT precisa ler.
- Qual modificador aplica.
- Se e core ou opcional.
- Se o mestre pode ativar/desativar por campanha/cena.

## Validacao antes de entregar

- Comparar cada entrada com o banco atual por slug e nome.
- Rodar `manage.py validate_tags` quando houver tags novas.
- Conferir que nenhum item/criatura foi duplicado por fonte antiga.
- Listar criaturas que nao puderam ser extraidas com seguranca para import manual.
- Listar paginas/fontes problemáticas no manifesto.

## Observacao importante

O objetivo e alimentar o backend por dados e tags. Se uma mecanica parecer exigir codigo especial, registre a necessidade no manifesto em vez de hardcodar no import.
