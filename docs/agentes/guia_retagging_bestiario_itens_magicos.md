# Guia para retagging do Bestiario e Itens Magicos

Este guia e para o agente que vai aprofundar as tags mecanicas de
`TB_Bestiario` e `TB_ItemMagico`.

Regra central: `tags_json` nao e etiqueta de catalogo. E uma linguagem de
mecanica, parecida com formula de Excel. Se o dado ja existe como coluna de
cadastro, nao vire tag. Se o dado muda rolagem, estado, contador, acao,
resistencia, conjuracao, ataque, alvo ou condicao, ele precisa virar tag.

Use tambem:

- `docs/agentes/regras_retagging_tags_json.md`
- `docs/criador-personagem/vocabulario-tags-json.md`
- `docs/criador-personagem/dicionario-tags.md`
- `home/tag_library.json`

## 1. Regras gerais

- Identificadores mecanicos em `snake_case`.
- Nao usar hifen em nome de tag ou variavel mecanica. `-` fica reservado para
  subtracao/formula.
- Nao criar verbo ultra especifico se uma composicao generica resolve.
- Nao usar `source`, `fonte`, livro, pagina, importador ou metadado editorial
  como tag.
- Ordem importa. Restricoes dentro de um bloco so afetam aquele bloco.
- `restriction{...}` bloqueia o uso/aplicacao do escopo.
- `restricts{...}` e uma proibicao imposta por um efeito ativo.
- `requires{...}` e pre-condicao positiva.

## 2. Bestiario: objetivo

Toda criatura precisa ter as mecanicas do statblock representadas em tags.
O `statblock_json` continua sendo a ficha importada/renderizavel, mas
`tags_json` e a versao executavel para ficha, exportador e futuro VTT.

Nao basta taggear conjuracao. Tambem entram:

- atributos e modificadores que afetam rolagens;
- CA, PV, deslocamentos e sentidos quando usados mecanicamente;
- saves e pericias;
- resistencias, imunidades, vulnerabilidades e imunidades a condicao;
- tracos passivos;
- acoes, bonus actions, reacoes, lendarias e miticas;
- ataques corpo a corpo, a distancia, naturais, armas, magia;
- dano, alcance, area, alvo, CD, save e resultado no sucesso/falha;
- recarga, usos, cargas, reset e frequencia;
- auras, emanacoes, luz, telepatia, fala, sentidos compartilhados;
- conjuracao preparada/inata/psionica;
- summon/companheiro e escala com dono.

### Nao transformar em tag de criatura

- nome;
- slug;
- fonte/livro/pagina;
- texto de flavor que nao altera mecanica;
- descricao repetida que so serve para display.

Tipo, tamanho e ND sao campos do bestiario, mas podem entrar em tag quando o
motor precisar deles como regra executavel ou filtro dinamico. Ex.: familiar
usa "qualquer besta CR 0"; nesse caso o resolvedor pode derivar do campo ou a
tag pode explicitar seletores, desde que o padrao seja consistente.

## 3. Bestiario: formato recomendado

Organize por blocos:

```text
stats{
  str:16, dex:14, con:15, int:8, wis:12, cha:10,
  ca:15,
  hp:45,
  speed{walk:30ft, fly:60ft}
}
saves{dex:+5, con:+4}
skills{percepcao:+4, furtividade:+6}
senses{darkvision:60ft, passive_perception:14}
resist{frio, fogo}
immune{veneno}
cond_immune{envenenado}
trait{nome_slug, always_active{...}}
action{multiattack, attacks:=2}
attack{
  name:mordida,
  type:melee_natural,
  atk:+6,
  reach:5ft,
  target:one,
  hit{dmg:1d8+4(perfurante)}
}
reaction{aparar, trigger=hit_by_melee, ca:+2(against:attack)}
```

Se a biblioteca ainda nao tiver exatamente `stats{}`, `skills{}` ou
`attack{}` neste formato, o agente deve propor/registrar no relatorio antes de
massificar. O objetivo e evitar 50 tags especificas como
`percepcao_passiva`, `mordida_dano`, `garra_ataque`.

### Conjuracao de criatura

Conjuracao deve ficar taggeada, nao apenas no texto.

Exemplos:

```text
spellcasting{
  ability:int,
  cd:16,
  atk:+8,
  caster_level:9,
  prepared{
    0:[firebolt],
    1:[shield],
    2:[scorching_ray],
    3:[haste]
  },
  slots{1:4, 2:3, 3:3}
}
```

Conjuracao inata:

```text
cast{spell:misty_step, modifiers{no_slot}, uses{3, reset:day}}
cast{spell:plane_shift, modifiers{no_slot}, uses{1, reset:day}}
```

Se a criatura usa magia sem slot por traco, use `cast{... uses{...}}` para a
linha aparecer como `1/day`, `3/day`, etc.

### Ataques e acoes

Cada ataque precisa dizer:

- tipo de ataque: `melee`, `ranged`, `natural`, `weapon`, `magic`;
- bonus de ataque;
- alcance/reach;
- alvo;
- dano e tipo;
- efeitos extras, saves e condicoes.

Exemplo:

```text
attack{
  name:rede,
  type:ranged_weapon,
  atk:+7,
  range:30ft/120ft,
  target:one,
  hit{
    dmg:1d6+4(perfurante),
    apply:restringido,
    escape{action=action, save{str, cd=12}},
    break{ca:10, hp:5}
  }
}
```

Multiattack nao deve ser texto solto:

```text
action{multiattack, attacks{garra:2}}
```

ou, quando for condicional:

```text
action{multiattack, match(forma){besta:{attacks{mordida:1, garra:1}}, default:{attacks{espada:2}}}}
```

## 4. Itens magicos: objetivo

Itens magicos devem seguir o mesmo criterio que foi aplicado aos itens
mundanos: tag e mecanica, nao cadastro.

Remover/nao criar tags que so repetem colunas:

```text
item:magico
raridade:...
slot:...
loja:...
tipo:...
source:...
fonte:...
```

`requer_sintonizacao` e `detalhes_sintonizacao` ja existem no banco. Nao use
`sintonizacao` so para espelhar a coluna. Use tags apenas quando houver efeito
mecanico relacionado, por exemplo:

```text
requires{classe:clerigo | classe:paladino}
attr_max:sintonizacao=6
```

## 5. Itens magicos: o que taggear

Para cada item, leia a descricao e extraia apenas o que o motor precisa executar:

- bonus de ataque/dano;
- bonus de CA;
- bonus de CD ou ataque de magia;
- vantagem/desvantagem;
- resistencia, imunidade, vulnerabilidade;
- imunidade a condicao;
- alteracao de atributo, teto ou pericia;
- proficiencia/expertise;
- velocidade, voo, nado, escalada, teleporte;
- sentidos, telepatia, idiomas;
- luz/visao;
- cargas e reset;
- consumivel;
- conjurar magia pelo item;
- salvar CD, dano, cura, area e condicao;
- efeitos ativados por action/bonus_action/reaction;
- gatilhos;
- restricoes e pre-requisitos de uso;
- criacao/invocacao de criatura ou objeto;
- transformacao de arma/armadura, propriedade especial, retorno, tipo de dano.

Exemplos:

```text
weapon.atk:+1
weapon.dmg:+1
```

```text
ca:+1
```

```text
spell.atk:+1
spell.cd:+1
```

```text
charges:7(reset:dawn, regain:1d6+1)
cast{spell:bola_de_fogo, modifiers{no_slot}, charge_cost:3}
```

```text
always_active{resist:veneno, adv:save{contra:veneno}}
```

```text
action=action
instant{aoe{sphere:20ft, save{dex, cd=15}, dmg:7d6(fogo), on_success:half}}
consumable
```

## 6. Prioridade sugerida

### Bestiario

1. Criaturas sem tags e com conjuracao.
2. Criaturas invocadas por magias ou habilidades.
3. Companheiros de classe/subclasse que escalam com dono.
4. Criaturas com resistencia/imunidade/condicao.
5. Criaturas com ataques que aplicam condicoes.
6. Criaturas com recharge, aura, legendary action ou reaction.
7. Criaturas simples de baixo ND.

### Itens magicos

1. Itens com tags apenas de metadado.
2. Itens com cargas/uses/reset.
3. Itens que conjuram magias.
4. Armas, armaduras e escudos com bonus.
5. Itens com resistencia/imunidade/vantagem.
6. Itens com efeitos ativados, save/CD/dano/condicao.
7. Itens de flavor sem mecanica real: deixar tags vazias ou so a tag mecanica
   minima, nunca inventar efeito.

## 7. Validacao obrigatoria

Antes de comecar, o agente deve incluir `TbItemMagico` no comando
`validate_tags`, porque hoje o relatorio padrao pode deixar item magico passar.

Rodar:

```powershell
$env:DB_ENGINE='django.db.backends.sqlite3'
Remove-Item Env:POSTGRES_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe manage.py validate_tags --strict-names
```

Se estiver usando PostgreSQL local funcional, pode rodar sem forcar SQLite.

Relatorio esperado no fim:

- total de criaturas alteradas;
- total de itens magicos alterados;
- itens/criaturas deixados sem tag e motivo;
- verbos novos propostos;
- verbos desconhecidos restantes;
- exemplos revisados manualmente;
- lista de pendencias para PO.

## 8. Checklist final

- Nada de `source`/livro/pagina em tags.
- Nada de `item:magico`, `raridade`, `slot`, `loja`, `tipo` como tags mecanicas.
- Nenhum identificador mecanico com hifen.
- Criaturas com ataques, acoes, saves, pericias, resistencias, imunidades,
  condicoes e conjuracao representados em tags.
- Itens magicos com tags equivalentes ao que a descricao faz, nao ao que a
  tabela ja sabe.
- `validate_tags --strict-names` sem erros.
- Amostra manual revisada: pelo menos 20 criaturas e 20 itens de alta
  complexidade.
