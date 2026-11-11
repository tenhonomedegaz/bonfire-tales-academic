# Pipeline para traducao e revisao de itens e criaturas

Objetivo: deixar todos os itens mundanos, itens magicos e criaturas com nome e descricao/statblock em portugues, sem quebrar as tags mecanicas. Este trabalho deve preservar a ideia central do projeto: o backend deve continuar movido por `tags_json`, nao por excecoes hardcoded em views, builder ou ficha.

## Escopo

Inclui:

- `TbItemMundano`: nome, descricao em markdown e campos estruturados derivados de `ref/Livros/Items.csv`.
- `TbItemMagico`: nome, descricao em markdown e campos estruturados derivados de `scratch/import_itens/itens_descricoes_en.csv`.
- `TbBestiario`: nome, tipo, tamanho, alinhamento, descricao em markdown, `statblock_json` exibivel e tags basicas de criatura.
- `tags_json` dos itens e criaturas, somente quando a traducao revelar mecanica que precisa ser expressa por tag.
- Fixtures em `home/fixtures/conteudo.json` e `home/fixtures/conteudo_manifest.json`.

Nao inclui:

- Magias, exceto referencias de nomes de magias dentro de itens.
- Fonte/page em item ou criatura. Fonte e pagina sao referencia de importacao, nao conteudo exibido.
- Regras hardcoded no character builder, ficha, views ou templates.

## Arquivos de entrada

- Itens mundanos: `ref/Livros/Items.csv`
- Itens magicos: `scratch/import_itens/itens_descricoes_en.csv`
- Criaturas oficiais selecionadas: `ref/Livros/Bestiary_selecao.csv`
- Bestiario bruto/apoio: `ref/Livros/Bestiary.csv`, `ref/Livros/Monster Manual (2025).md`, `ref/Livros/Monster Manual (2014).md`, `ref/dnd-data-main/data/monsters.json`
- Mapa de magias EN/PT, quando existir:
  - `ref/Livros/magias_en_pt.csv`
  - `ref/Livros/magias_alinhado.csv`

## Comandos existentes

Use SQLite nesta etapa, a menos que o mantenedor peça outro banco:

```powershell
$env:DB_ENGINE='sqlite'
```

Refinar mundanos:

```powershell
.\.venv\Scripts\python.exe manage.py refinar_itens_mundanos_csv --apply
```

Refinar magicos:

```powershell
.\.venv\Scripts\python.exe manage.py refinar_itens_magicos_csv --apply
```

Gerar tags:

```powershell
.\.venv\Scripts\python.exe manage.py taggear_itens --tipo todos --apply
```

Importar/refinar criaturas:

```powershell
.\.venv\Scripts\python.exe manage.py importar_bestiario_csv --apply
```

Gerar tags basicas de criaturas:

```powershell
.\.venv\Scripts\python.exe manage.py gerar_tags_bestiario --apply
```

Exportar fixture:

```powershell
.\.venv\Scripts\python.exe manage.py dump_conteudo --output home/fixtures/conteudo.json --manifest home/fixtures/conteudo_manifest.json
```

Validar Django:

```powershell
.\.venv\Scripts\python.exe manage.py check
```

## Ordem recomendada

1. Rode uma auditoria inicial de tags e idioma.
2. Corrija primeiro os tradutores/normalizadores, nao item por item.
3. Reaplique os comandos de refinamento/importacao.
4. Reaplique `taggear_itens` e `gerar_tags_bestiario`.
5. Rode validacao formal das tags.
6. Rode auditoria de idioma.
7. Corrija os casos restantes por lote.
8. Exporte fixture.
9. Entregue relatorio com contagens antes/depois e lista de pendencias reais.

## Regra de ouro

Nao traduza so com substituicao palavra a palavra. O resultado atual dos itens magicos tem muito texto hibrido, como `While holding this wand, voce pode...`. Isso precisa virar portugues natural de regra:

- `While holding this wand, you gain...`
- `Enquanto segura esta varinha, voce recebe...`

Use vocabulario consistente:

- `Armor Class` -> `CA`
- `attack roll` -> `jogada de ataque`
- `damage roll` -> `rolagem de dano`
- `saving throw` -> `teste de resistencia`
- `spell save DC` -> `CD de resistencia de magia`
- `spell attack roll` -> `jogada de ataque de magia`
- `charges` -> `cargas`
- `regains ... expended charges daily at dawn` -> `recupera ... cargas gastas diariamente ao amanhecer`
- `requires attunement` -> `requer sintonizacao`
- `while wearing` -> `enquanto usa/veste`
- `while holding` -> `enquanto segura`
- `as a Magic action` -> `como uma acao magica`
- `bonus action` -> `acao bonus`
- `reaction` -> `reacao`
- `creature` -> `criatura`
- `target` -> `alvo`
- `Hit Points` -> `pontos de vida`
- `temporary Hit Points` -> `pontos de vida temporarios`

## Medidas e alcance

Padrao do projeto: toda distancia/alcance/deslocamento exibivel deve trazer metros e feet.

Use este formato:

- distancia simples: `9 m (30 ft.)`
- alcance corpo a corpo: `1,5 m (5 ft.)`
- alcance com curto/longo: `18/36 m (60/120 ft.)`
- deslocamento: `9 m (30 ft.)`, `voo 18 m (60 ft.)`, `nado 12 m (40 ft.)`
- area/raio/cone/linha: `raio de 6 m (20 ft.)`, `cone de 4,5 m (15 ft.)`, `linha de 18 m (60 ft.)`

Conversao padrao: `1 ft. = 0,3 m`; nos valores de D&D, use o arredondamento tradicional:

- `5 ft.` -> `1,5 m`
- `10 ft.` -> `3 m`
- `15 ft.` -> `4,5 m`
- `20 ft.` -> `6 m`
- `30 ft.` -> `9 m`
- `60 ft.` -> `18 m`
- `120 ft.` -> `36 m`
- `300 ft.` -> `90 m`

Importante: as tags e formulas internas podem continuar usando `ft`, porque o DSL trabalha melhor com a unidade original do sistema. A regra acima e para texto exibivel em markdown/statblock/card.

## Nomes

Os nomes devem ficar em portugues quando houver traducao obvia ou ja usada no banco.

Exemplos que foram detectados como pendentes:

- `Armor of Etherealness`
- `Boots of Haste`
- `Boots of the Vigilant`
- `Echo Stone`
- `Flamefriend Lantern`
- `Luck Weapon`
- `Mirror of Infinite Transpondence`
- `Oceanic Weapon`
- `Ring of Protection +2`
- `Rod of Mercurial Form`
- `Stormrider Boots`
- `Vorpal Weapon`

Casos especiais:

- `Ioun Stone` pode permanecer como nome proprio se essa for a convencao do projeto, mas o subtitulo deve ser normalizado: `Pedra Ioun, Forca` ou `Ioun Stone, Forca`, sem misturar ingles comum como `Insight` se houver traducao.
- `Manual de ...` ja esta em portugues e nao deve ser marcado como erro so porque contem a palavra `Manual`.
- Nao altere slugs sem necessidade. Slug serve para casar dados e referencias.

## Mundanos

Problema principal atual: as descricoes estao majoritariamente em portugues, mas o bloco `### Dados oficiais` ainda traz taxonomia inglesa:

- `Weapon`
- `Simple Weapon`
- `Martial Weapon`
- `Melee Weapon`
- `Ranged Weapon`
- `Adventuring Gear`
- `Light Armor`
- `Medium Armor`
- `Heavy Armor`
- `Spellcasting Focus`
- `Artisan's Tools`
- `Gaming Sets`
- `Musical Instruments`
- `Mounts and Vehicles`

Corrija em `refinar_itens_mundanos_csv.py` usando mapas estruturados, nao substituicao solta em markdown final. O bloco final deve sair assim:

```markdown
### Dados oficiais
- **Tipo:** Arma, Arma Simples, Arma Corpo a Corpo
- **Preco:** 2 PO
- **Peso:** 1 lb.
```

Tambem revisar propriedades ainda em ingles:

- `Two-Handed` -> `Duas Maos`
- `Loading` -> `Carregar`
- `Ammunition` -> `Municao`
- `Reach` -> `Alcance`
- `Thrown` -> `Arremesso`

Atencao: `PO`, `PP`, `PC` sao moedas em portugues e nao sao erro de idioma.

## Magicos

Problema principal atual: quase todas as descricoes magicas ainda tem residuos ingleses. O comando `refinar_itens_magicos_csv.py` hoje usa uma lista grande de regex; isso ajuda, mas gera frases hibridas. O outro agente deve preferir uma destas abordagens:

1. Traduzir por blocos/frases frequentes, mantendo regex apenas para padroes mecanicos.
2. Gerar uma tabela intermediaria `slug -> descricao_pt` revisada em lotes.
3. Melhorar `translate()` para reconhecer paragrafos inteiros e nao apenas palavras.

O CSV de entrada deve ser usado assim:

- usar `db_slug` para encontrar o item;
- usar `description_en` como texto fonte;
- ignorar `source`, `page` e campos similares no conteudo final;
- nao inserir `**Fonte:**` nas descricoes.

## Criaturas

Problema principal atual: o bestiario esta em portugues parcial. A estrutura esta em PT-BR (`CA`, `PV`, `Deslocamento`, `Pericias`, `Sentidos`, `Idiomas`, `Acoes`), mas muitos valores exibiveis ainda estao em ingles.

Na ultima auditoria local havia:

- `924` criaturas em `TbBestiario`.
- `108` nomes com ingles aparente.
- `365` campos `tipo` com ingles.
- `5` campos `alinhamento` com ingles.
- `588` descricoes markdown com residuo ingles exibivel.

Exemplos de nomes pendentes:

- `Air Elemental`
- `Barbed Devil`
- `Beast of the Land`
- `Giant Frog`
- `Goblin Boss`
- `Mummy Lord`
- `Riding Horse`

Exemplos de tipo pendente:

- `Dragon (Gem)` -> `Dragao (Gema)`
- `Dragon (Chromatic)` -> `Dragao (Cromatico)`
- `Dragon (Metallic)` -> `Dragao (Metalico)`
- `Fiend (Demon)` -> `Corruptor (Demonio)`
- `Fiend (Devil)` -> `Corruptor (Diabo)`
- `Beast (Dinosaur)` -> `Besta (Dinossauro)`
- `Humanoid (Wizard)` -> `Humanoide (Mago)`

Campos a traduzir:

- `nome`
- `tipo`
- `tamanho`
- `alinhamento`
- `descricao_markdown`
- partes exibiveis de `statblock_json`, como `name`, `type`, `size`, `alignment`, `speed`, `saving_throws`, `skills`, `senses`, `languages`, nomes de tracos, acoes, reacoes, bonus actions, legendary actions, lair actions e regional effects.

Campos que podem permanecer em ingles se forem referencia interna de importacao:

- `name_en`
- `type_en`
- `alignment_en`
- `label_en`
- `spell_refs[*].name_en`
- outros campos explicitamente terminados em `_en`

Nao remova campos `_en` se eles ajudam a rastrear a origem. O problema e ingles no conteudo que o site/card/statblock usa para exibir.

Vocabulario recomendado para statblocks:

- `Tiny` -> `Minimo`
- `Small` -> `Pequeno`
- `Medium` -> `Medio`
- `Large` -> `Grande`
- `Huge` -> `Enorme`
- `Gargantuan` -> `Colossal`
- `Aberration` -> `Aberracao`
- `Beast` -> `Besta`
- `Celestial` -> `Celestial`
- `Construct` -> `Construto`
- `Dragon` -> `Dragao`
- `Elemental` -> `Elemental`
- `Fey` -> `Feerico`
- `Fiend` -> `Corruptor`
- `Giant` -> `Gigante`
- `Humanoid` -> `Humanoide`
- `Monstrosity` -> `Monstruosidade`
- `Ooze` -> `Limo`
- `Plant` -> `Planta`
- `Undead` -> `Morto-vivo`
- `Common` -> `Comum`
- `Draconic` -> `Draconico`
- `Deep Speech` -> `Dialeto Subterraneo`
- `Sylvan` -> `Silvestre`
- `telepathy` -> `telepatia`
- `passive Perception` -> `Percepcao passiva`
- `darkvision` -> `visao no escuro`
- `blindsight` -> `percepcao as cegas`
- `truesight` -> `visao verdadeira`
- `hover` -> `pairar`
- `Fly` -> `voo`
- `Swim` -> `nado`
- `Burrow` -> `escavacao`
- `Climb` -> `escalada`
- `Recharge` -> `Recarga`
- `Multiattack` -> `Ataques Multiplos`
- `Bite` -> `Mordida`
- `Claw` -> `Garra`
- `Tail` -> `Cauda`
- `Slam` -> `Pancada`
- `Breath` -> `Sopro`

Tipos de dano e condicoes devem ficar em portugues no texto exibivel:

- `acid` -> `acido`
- `cold` -> `frio`
- `fire` -> `fogo`
- `force` -> `forca`
- `lightning` -> `eletrico`
- `necrotic` -> `necrotico`
- `poison` -> `veneno`
- `psychic` -> `psiquico`
- `radiant` -> `radiante`
- `thunder` -> `trovejante`
- `bludgeoning` -> `concussao`
- `piercing` -> `perfurante`
- `slashing` -> `cortante`
- `blinded` -> `cego`
- `charmed` -> `enfeiticado`
- `deafened` -> `surdo`
- `frightened` -> `amedrontado`
- `grappled` -> `agarrado`
- `incapacitated` -> `incapacitado`
- `invisible` -> `invisivel`
- `paralyzed` -> `paralisado`
- `petrified` -> `petrificado`
- `poisoned` -> `envenenado`
- `prone` -> `caido`
- `restrained` -> `contido`
- `stunned` -> `atordoado`
- `unconscious` -> `inconsciente`

Ao traduzir criaturas, prefira melhorar `importar_bestiario_csv.py` e/ou um comando de refinamento de bestiario. Evite editar registros individualmente salvo para excecoes documentadas.

Regra para magias em criaturas:

- nomes das magias exibidos devem usar o nome PT do banco;
- referencias mecanicas devem continuar como `spell:<slug>` ou tags `cast{spell:<slug>, ...}`;
- se a magia nao resolver para `TbMagia.slug`, registre a pendencia no relatorio.

## Tags durante traducao

Traducao nao pode remover informacao mecanica que o tagger usa. Depois de traduzir, rode `taggear_itens`.

Tags importantes esperadas:

- Todo item: `item:mundano` ou `item:magico`
- Toda criatura: tags basicas de `gerar_tags_bestiario`, incluindo tipo/tamanho/ND/deslocamento/sentidos/resistencias/imunidades/conjuracao quando o comando suportar.
- Mundanos:
  - armas: `dmg:*`, `add-property:*`, `maestrias{...}`
  - armaduras: `ca=*` ou `ca:+*`, `dex-ca-max:*`, `dadv:furtividade` quando aplicavel
  - venenos, municoes, explosivos, comida consumivel: `consumable`
  - kit de curandeiro: `charges:10(reset:none)`
- Magicos:
  - sintonizacao: `sintonizacao`
  - cargas: `charges:N(reset:dawn|daily|none)`
  - pocoes, pergaminhos, municoes e itens gastos: `consumable`
  - bonus de arma: `weapon.atk:+N`, `weapon.dmg:+N`
  - bonus de CA: `ca:+N`
  - bonus de magia: `spell.atk:+N`, `spell-save-cd:+N`
  - conjuracao por item: `cast{spell:<slug>, modifiers{no-slot}, ...}`

Nao crie tags novas por impulso. Se uma mecanica nao couber no dicionario, documente a necessidade e atualize `home/tag_library.json` com exemplo e semantica clara.

## Auditoria de tags

Use este script depois de cada rodada relevante:

```powershell
$env:DB_ENGINE='sqlite'
$env:PYTHONIOENCODING='utf-8'
@'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','bonfire.settings')
import django; django.setup()
from collections import Counter
from home.models import TbItemMundano, TbItemMagico, TbBestiario
from home.tag_engine import Library, DataIndex, validate_tags_json

lib = Library()
data = DataIndex.build()
counts = Counter()
samples = []

for model, qs in [
    ('mundano', TbItemMundano.objects.all()),
    ('magico', TbItemMagico.objects.all()),
    ('bestiario', TbBestiario.objects.all()),
]:
    for obj in qs.order_by('slug'):
        for d in validate_tags_json(obj.tags_json, lib, data):
            counts[(model, d.level, d.code)] += 1
            if len(samples) < 80:
                samples.append((model, obj.slug, obj.nome, d.level, d.code, d.message, d.fragment))

print('COUNTS')
for k, v in sorted(counts.items()):
    print(k, v)
print('SAMPLES')
for s in samples:
    print('\t'.join(map(str, s)))
print('EMPTY_TAGS',
      sum(1 for i in TbItemMundano.objects.all() if not i.tags_json),
      sum(1 for i in TbItemMagico.objects.all() if not i.tags_json),
      sum(1 for i in TbBestiario.objects.all() if not i.tags_json))
'@ | .\.venv\Scripts\python.exe
```

Criterio de aceite: `COUNTS` vazio e `EMPTY_TAGS 0 0 0`.

## Auditoria semantica minima

Use este script para pegar inconsistencias obvias:

```powershell
$env:DB_ENGINE='sqlite'
$env:PYTHONIOENCODING='utf-8'
@'
import os, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE','bonfire.settings')
import django; django.setup()
from home.models import TbItemMundano, TbItemMagico

def has(tags, prefix):
    return any(isinstance(t, str) and (t == prefix or t.startswith(prefix)) for t in (tags or []))

def slugish(value):
    return (value or '').lower().replace('_', '-').replace(' ', '-')

checks = {k: [] for k in [
    'magico_attunement_field_missing_tag',
    'magico_attunement_tag_without_field',
    'magico_structural_consumable_missing_tag',
    'magico_precise_charges_missing_tag',
    'magico_plus_shield_missing_ca_tag',
    'mundano_structural_consumable_missing_tag',
    'mundano_weapon_missing_mastery',
    'mundano_armor_missing_ca_tag',
]}

charge_rx = re.compile(r'\b(?:has|have|starts with|tem|possui|comeca com)\s+(\d+)\s+(?:charges|cargas)\b|\b(\d+)\s+(?:charges|cargas)\b', re.I)

for obj in TbItemMagico.objects.order_by('slug'):
    tags = obj.tags_json or []
    slot = slugish(obj.slot)
    tipo = slugish(obj.tipo)
    if obj.requer_sintonizacao and not has(tags, 'sintonizacao'):
        checks['magico_attunement_field_missing_tag'].append((obj.slug, obj.nome))
    if (not obj.requer_sintonizacao) and has(tags, 'sintonizacao'):
        checks['magico_attunement_tag_without_field'].append((obj.slug, obj.nome))
    if (slot in {'pocao', 'pergaminho', 'municao'} or tipo in {'pocao', 'pergaminho', 'municao'} or 'pocao' in tipo or 'pergaminho' in tipo or 'municao' in tipo) and not has(tags, 'consumable'):
        checks['magico_structural_consumable_missing_tag'].append((obj.slug, obj.nome, obj.slot, obj.tipo))
    if charge_rx.search(obj.descricao_markdown or '') and not has(tags, 'charges:'):
        checks['magico_precise_charges_missing_tag'].append((obj.slug, obj.nome))
    m = re.match(r'^\+(\d+)\s+Escudo', obj.nome or '', re.I)
    if m and not has(tags, f'ca:+{m.group(1)}'):
        checks['magico_plus_shield_missing_ca_tag'].append((obj.slug, obj.nome))

for obj in TbItemMundano.objects.order_by('slug'):
    tags = obj.tags_json or []
    cat = slugish(obj.categoria)
    sub = slugish(obj.subcategoria)
    if (cat in {'veneno', 'municao'} or sub.startswith('veneno') or sub == 'municao') and not has(tags, 'consumable'):
        checks['mundano_structural_consumable_missing_tag'].append((obj.slug, obj.nome, obj.categoria, obj.subcategoria))
    if cat == 'arma' and not has(tags, 'maestrias'):
        checks['mundano_weapon_missing_mastery'].append((obj.slug, obj.nome))
    if cat == 'armadura' and not (has(tags, 'ca=') or has(tags, 'ca:+')):
        checks['mundano_armor_missing_ca_tag'].append((obj.slug, obj.nome))

for key, rows in checks.items():
    print(key, len(rows))
    for row in rows[:40]:
        print('\t'.join(map(str, row)))
'@ | .\.venv\Scripts\python.exe
```

Criterio de aceite: todos os contadores devem ser `0`.

## Auditoria de criaturas

Use este script para verificar se o bestiario ainda tem ingles no conteudo exibivel. Ele ignora a ideia de que campos `_en` podem continuar existindo como referencia interna, mas flagra `nome`, `tipo`, `tamanho`, `alinhamento` e `descricao_markdown`.

```powershell
$env:DB_ENGINE='sqlite'
$env:PYTHONIOENCODING='utf-8'
@'
import os, re
from collections import Counter
os.environ.setdefault('DJANGO_SETTINGS_MODULE','bonfire.settings')
import django; django.setup()
from home.models import TbBestiario

NAME_RX = re.compile(r'\b(ancient|adult|young|wyrmling|dragon|giant|goblin|orc|kobold|skeleton|zombie|wraith|spirit|beast|demon|devil|angel|elemental|construct|ooze|swarm|bat|cat|rat|raven|spider|wolf|bear|eagle|hawk|owl|frog|lizard|snake|horse|mastiff|ape|tiger|lion|boar|crocodile|shark|octopus|elk|deer|goat|hyena|weasel|vulture|scorpion|centipede|crab|badger|panther|rhinoceros|elephant|mammoth|dinosaur|tyrannosaurus|pteranodon|sahuagin|merfolk|cultist|guard|bandit|mage|priest|knight|assassin|spy|noble|commoner|veteran|warrior|archer|captain|boss|lord|king|queen|hunter|leader|warlock|wizard|sorcerer|druid|bard|monk|paladin|ranger|fighter|rogue|cleric|barbarian|breath|claw|bite|tail|slam|strike|gaze|aura)\b', re.I)
TYPE_RX = re.compile(r'\b(aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant|humanoid|monstrosity|ooze|plant|undead|demon|devil|wizard|cleric|druid|paladin|goblinoid|dinosaur|titan|gem|chromatic|metallic|lawful|neutral|evil|good|chaotic|unaligned)\b', re.I)
DESC_RX = {
    'stat_headers_en': re.compile(r'\b(Armor Class|Hit Points|Speed|Saving Throws|Skills|Senses|Languages|Challenge|Actions|Bonus Actions|Reactions|Legendary Actions|Multiattack|Melee Weapon Attack|Ranged Weapon Attack|Hit:|Recharge|Spellcasting|Innate Spellcasting)\b', re.I),
    'rule_words_en': re.compile(r'\b(creature|target|saving throw|attack roll|damage roll|spell save DC|advantage|disadvantage|condition|while|within|until|takes|deals|must|can|has|make|makes|use|uses|target|hit points|speed|feet|ft\.)\b', re.I),
    'conditions_damage_en': re.compile(r'\b(blinded|charmed|deafened|frightened|grappled|incapacitated|invisible|paralyzed|petrified|poisoned|prone|restrained|stunned|unconscious|acid|cold|fire|force|lightning|necrotic|poison|psychic|radiant|thunder|bludgeoning|piercing|slashing)\b', re.I),
}

summary = Counter()
samples = {k: [] for k in ['nome', 'tipo', 'tamanho', 'alinhamento', 'descricao']}

for obj in TbBestiario.objects.order_by('slug'):
    summary['total'] += 1
    if NAME_RX.search(obj.nome or ''):
        summary['nome_en_like'] += 1
        if len(samples['nome']) < 80:
            samples['nome'].append((obj.slug, obj.nome))
    for field in ['tipo', 'tamanho', 'alinhamento']:
        val = getattr(obj, field) or ''
        if TYPE_RX.search(val):
            summary[f'{field}_en_like'] += 1
            if len(samples[field]) < 40:
                samples[field].append((obj.slug, obj.nome, val))
    desc = obj.descricao_markdown or ''
    hit = False
    for key, rx in DESC_RX.items():
        m = rx.search(desc)
        if m:
            summary[f'desc_{key}'] += 1
            hit = True
    if hit:
        summary['descricao_en_like'] += 1
        if len(samples['descricao']) < 60:
            for key, rx in DESC_RX.items():
                m = rx.search(desc)
                if m:
                    a = max(0, m.start() - 80)
                    b = min(len(desc), m.end() + 140)
                    samples['descricao'].append((obj.slug, obj.nome, key, desc[a:b].replace('\n', ' / ')))
                    break

print('SUMMARY')
for k, v in sorted(summary.items()):
    print(k, v)
for key, rows in samples.items():
    print('\n##', key)
    for row in rows:
        print('\t'.join(map(str, row)))
'@ | .\.venv\Scripts\python.exe
```

Criterio de aceite: contadores de `*_en_like` e `descricao_en_like` proximos de `0`, exceto nomes proprios justificados no relatorio.

## Auditoria de idioma

Use a auditoria abaixo como heuristica. Ela nao substitui revisao humana, mas aponta residuos ingleses:

```powershell
$env:DB_ENGINE='sqlite'
$env:PYTHONIOENCODING='utf-8'
@'
import os, re
from collections import Counter
os.environ.setdefault('DJANGO_SETTINGS_MODULE','bonfire.settings')
import django; django.setup()
from home.models import TbItemMundano, TbItemMagico

PATTERNS = {
    'pronome_en': r'\b(you|your|yours|yourself)\b',
    'artigos_en': r'\b(the|an|this|these|those|that)\b',
    'verbos_en': r'\b(can|cannot|must|may|gain|gains|have|has|wear|wield|use|roll|make|take|cast|target|choose|regain|expend|deal|deals|increase|reduced)\b',
    'termos_magia_en': r'\b(spell|spells|spellcasting|cantrip|slot|slots|charge|charges|save|saving throw|attack roll|damage roll|modifier|DC|hit points|temporary hit points)\b',
    'termos_item_en': r'\b(weapon|armor|shield|wand|staff|rod|ring|potion|scroll|wondrous item|requires attunement|attunement|rarity|bonus|property|properties)\b',
    'taxonomy_en': r'\b(Weapon|Simple Weapon|Martial Weapon|Melee Weapon|Ranged Weapon|Armor|Light Armor|Medium Armor|Heavy Armor|Adventuring Gear|Tools|Artisan\'s Tools|Gaming Sets|Musical Instruments|Mounts and Vehicles|Tack, Harness, and Drawn Vehicles)\b',
    'frases_en': r'\b(while wearing|while holding|when you|whenever you|as an action|bonus action|reaction|once per day|at dawn|roll a d20|requires attunement)\b',
}
RX = {k: re.compile(v, re.I) for k, v in PATTERNS.items()}
NAME_RX = re.compile(r'\b(weapon|armor|shield|wand|staff|rod|ring|potion|scroll|cloak|boots|gloves|robe|amulet|bag|deck|tome|book|instrument|horn|helm|belt|bracers|brooch|candle|carpet|chime|crystal|cube|dust|gem|figurine|flask|goggles|lantern|medallion|mirror|necklace|orb|periapt|quiver|rope|scarab|stone|talisman|vial|wings)\b', re.I)

summary = Counter()
patterns = Counter()
names = []

for model, qs in [('mundano', TbItemMundano.objects.all()), ('magico', TbItemMagico.objects.all())]:
    summary[(model, 'total')] = qs.count()
    for obj in qs.order_by('slug'):
        if NAME_RX.search(obj.nome or ''):
            summary[(model, 'name_hits')] += 1
            if len(names) < 100:
                names.append((model, obj.slug, obj.nome))
        hit = False
        for key, rx in RX.items():
            if rx.search(obj.descricao_markdown or ''):
                patterns[(model, key)] += 1
                hit = True
        if hit:
            summary[(model, 'desc_hits')] += 1

print('SUMMARY')
for k, v in sorted(summary.items()):
    print(k, v)
print('PATTERNS')
for k, v in sorted(patterns.items()):
    print(k, v)
print('NAMES')
for row in names:
    print('\t'.join(row))
'@ | .\.venv\Scripts\python.exe
```

Criterio de aceite ideal:

- `magico desc_hits`: proximo de `0`.
- `mundano desc_hits`: proximo de `0`, ignorando falsos positivos documentados.
- `name_hits`: apenas nomes proprios aceitaveis, com justificativa no relatorio.

## Cuidados com falsos positivos

- `PO`, `PP`, `PC`, `PE` nao sao ingles.
- `Manual` em portugues nao e erro.
- `Ioun` pode ser nome proprio.
- Slugs ficam em ingles em muitos casos e nao sao problema.
- Tags ficam em slug ASCII e nao sao texto exibido.
- Campos de referencia de importacao nao devem entrar no markdown.
- Campos internos terminados em `_en` no `statblock_json` podem permanecer se nao forem usados como texto exibivel.
- `ft.` nao e erro quando aparece junto de metros no padrao `9 m (30 ft.)`; `30 ft.` sozinho no texto exibivel ainda precisa ser corrigido.

## Criterios de aceite final

O trabalho so esta completo quando:

- Todos os itens mundanos, itens magicos e criaturas tem `tags_json`.
- O validador de tags retorna `COUNTS` vazio.
- A auditoria semantica minima retorna tudo `0`.
- A auditoria de criaturas nao encontra ingles exibivel relevante em nome, tipo, tamanho, alinhamento ou descricao.
- `manage.py check` passa.
- `home/fixtures/conteudo.json` e `home/fixtures/conteudo_manifest.json` foram regenerados.
- Nomes, descricoes e statblocks exibiveis estao em portugues, exceto nomes proprios justificados.
- Alcances, areas e deslocamentos exibiveis mostram metros e ft., por exemplo `9 m (30 ft.)`.
- O relatorio final lista qualquer excecao restante por slug.

## Relatorio final esperado

O outro agente deve entregar:

- Quantidade de itens mundanos, itens magicos e criaturas revisados.
- Quantidade inicial/final de residuos ingleses.
- Lista de nomes que ficaram parcialmente em ingles e motivo.
- Lista de slugs que ainda precisam revisao humana, se houver.
- Comandos executados.
- Confirmacao de que nao foram adicionadas fontes ao conteudo dos itens ou criaturas.
- Confirmacao de que campos `_en` restantes sao somente referencia interna e nao texto exibivel.
- Confirmacao de que distancias/alcances/deslocamentos exibiveis estao em metros e ft.
- Confirmacao de que as tags continuam validas.
