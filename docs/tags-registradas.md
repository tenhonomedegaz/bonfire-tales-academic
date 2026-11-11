# Tags registradas

Auditoria feita em 2026-05-23 a partir do codigo do projeto. A consulta ao banco local nao foi possivel porque o PostgreSQL configurado em `POSTGRES_URL` nao respondeu em `localhost:5432`; portanto este documento lista as tags e categorias registradas/tratadas no codigo, nao os valores atualmente gravados no banco.

## Resumo

| Area | Campo | Situacao |
| --- | --- | --- |
| Missoes | `Quest.tags` | Tags livres informadas em `/missao-criar`; tambem ha tags tratadas pelo codigo. |
| Catalogo RPG | `RpgCatalogEntry.tags` | Campo existe no Prisma e e usado na busca por tag. |
| Itens | `Item` | Nao possui campo `tags`; busca usa `name`, `translatedName` e `type`. |
| Logs de personagem | `CharacterLog` | Nao possui campo `tags`; registra classe em `className`. |

## Tags de missao tratadas pelo codigo

| Tag | Origem | Uso |
| --- | --- | --- |
| `privada` | Criada automaticamente por `/missao-privada-criar` em `createPrivateQuest.ts`. | Identifica missao privada no campo `Quest.tags`. |
| `evento` | Informada manualmente em `/missao-criar` pelo campo `tags-missao`. | Em `questEmbeds.ts`, habilita recompensas extras de evento quando `tag.toLowerCase() === 'evento'`. |

Observacoes:

- `/missao-criar` aceita qualquer texto separado por virgula em `tags-missao`.
- Como o comando usa `questTags.split(",").map((t) => t.trim())`, uma missao criada sem tags pode salvar uma string vazia (`[""]`) em `Quest.tags`.
- `CreateQuestUseCase` nao normaliza nem valida tags; ele persiste o array recebido.

## Tags visuais nao persistidas

Estas labels aparecem na fila de missoes, mas nao sao salvas em campos `tags`:

| Label | Origem | Uso |
| --- | --- | --- |
| `Novato` | `questQueue.ts` | Exibida para inscrito novato. |
| `Colab` | `questQueue.ts` | Exibida para inscrito colaborador. |
| `Infrator` | `questQueue.ts` | Exibida para inscrito infrator. |

## Categorias do catalogo com tags

O modelo `RpgCatalogEntry` tem `tags String[] @default([])`, entao qualquer categoria cadastrada nele pode ter tags.

Categorias expostas hoje pelo comando `/rpg-consultar`:

| Categoria | Usa `RpgCatalogEntry.tags`? | Observacao |
| --- | --- | --- |
| `habilidade-racial` | Sim | Busca por `name`, `translatedName` e `tags has searchTerm`. |

Categorias de catalogo que existem no comando, mas nao usam `RpgCatalogEntry.tags`:

| Categoria | Fonte | Observacao |
| --- | --- | --- |
| `item` | Modelo `Item` | Sem campo `tags`; busca por nome traduzido, nome original e tipo. |
| `item-magico` | Modelo `Item` | Filtra `shopType` contendo `objetos magicos`; sem campo `tags`. |

## Faltas encontradas

| Falta | Evidencia | Impacto |
| --- | --- | --- |
| Categoria de magias nao registrada no comando | `ConsultaCategoria` em `rpgConsultar.ts` so aceita `item`, `item-magico` e `habilidade-racial`. | Mesmo que existam magias em `RpgCatalogEntry`, nao ha opcao no Discord para consultar `magia` por nome/tag. |
| Categoria de opcoes de classe nao registrada no comando | Nao ha choice como `opcao-classe`, `opcao-de-classe`, `class-option` ou equivalente. | Opcoes de classe com tags tambem nao seriam consultaveis pelo comando atual. |
| Help do catalogo incompleto para novas categorias | `help.ts` documenta apenas item, item magico e habilidade racial. | Ao adicionar magias/opcoes de classe, a ajuda precisa ser atualizada. |
| Itens nao possuem tags | Modelo `Item` nao tem `tags`; busca nao usa tag. | Tags de itens comuns/magicos precisariam migrar para `RpgCatalogEntry` ou adicionar `tags` em `Item`. |
| Tags de missao sem normalizacao | Tags manuais sao salvas como digitadas. | Pode haver duplicatas como `Evento`, `evento` e ` evento`; a regra de recompensa so normaliza na comparacao de evento. |

## Pontos de codigo auditados

- `prisma/schema.prisma`: `Quest.tags` e `RpgCatalogEntry.tags`.
- `src/modules/discord/commands/bonfire/rpg/rpgConsultar.ts`: categorias consultaveis e busca por tag do catalogo.
- `src/modules/discord/commands/bonfire/rpg/quests/createQuest.ts`: entrada manual `tags-missao`.
- `src/modules/discord/commands/bonfire/rpg/quests/createPrivateQuest.ts`: tag automatica `privada`.
- `src/modules/discord/commands/bonfire/rpg/quests/questEmbeds.ts`: regra da tag `evento`.
- `src/modules/discord/commands/bonfire/rpg/quests/questQueue.ts`: labels visuais `Novato`, `Colab` e `Infrator`.
- `src/modules/discord/commands/bonfire/help.ts`: categorias documentadas do catalogo.

## Consulta recomendada quando o banco estiver ativo

Para listar as tags realmente gravadas no banco:

```sql
select 'quest' as origem, tag, count(*) as usos
from rpg_quests, unnest(tags) as tag
where btrim(tag) <> ''
group by tag
union all
select category as origem, tag, count(*) as usos
from rpg_catalog_entries, unnest(tags) as tag
where btrim(tag) <> ''
group by category, tag
order by origem, tag;
```

