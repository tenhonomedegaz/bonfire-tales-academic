# Molduras de rank: concessao permanente e viseira

## Regra aprovada

Cada conta recebe duas molduras por patente alcancada com um personagem real:
`moldura-elo-<rank>-aberta` e `moldura-elo-<rank>-fechada`. Um rank superior
tambem libera os anteriores. A posse e da conta, pode ser usada em perfil e
fichas e nao altera a patente real de outro personagem.

A migration `0165_rank_themes` acrescenta um tema correspondente como terceira
recompensa de cada marco. Tambem troca Elo por Rank nos nomes visiveis, sem
renomear slugs ou alterar posses. Detalhes em `catalog-refresh.md`.

| Patente | Nivel do personagem | Aventuras minimas |
| --- | --- | --- |
| Obsidiana | 1 | 0 |
| Ametista | 5 | 9 |
| Topazio | 9 | 28 |
| Esmeralda | 13 | 59 |
| Ambar | 17 | 102 |
| Rubi | 20 | 140 |
| Diamante | 20 + patamar Epic Boon | 160 |

Lenda permanece titulo de Diamante, nao e uma oitava patente.

Personagem valido para esta regra: persistido, nivel entre 1 e 20, aventuras
nao negativas, ao menos uma classe, exatamente uma principal e soma dos niveis
de classe igual ao nivel da ficha. Ambos os marcos (build e aventuras) precisam
estar atingidos. Nao exige personagem publico nem ativo fora do cofre.

O laboratorio usa persistencia temporaria em transacao desfeita. Posses,
conquistas e notificacoes dessa simulacao sao desfeitas junto, sem callbacks
que escapem do rollback. Nao concede a partir de uma previa ou JSON de build.

Depois de concedida, a moldura permanece se o personagem perder nivel, for
arquivado ou excluido. Revogacoes e suspensoes explicitas da staff nao sao
reativadas automaticamente. Nao sao criadas ofertas ou precos.

## Implementacao e retroatividade

- Migration `0164_rank_cosmetic_rewards`: 14 registros de catalogo por chave
  natural, 7 conquistas `rank_reached` com `retention: permanent`, duas
  recompensas por conquista e backfill dos personagens existentes validos.
  Preserva PK, inventario, suspensoes, arte enviada e estado ativo preexistente.
- `home/rank_cosmetic_rewards.py`: validacao do build e reconciliacao idempotente.
- `home/signals.py`: criacao/atualizacao da ficha e das classes avaliam o marco
  dentro da mesma transacao. Leituras do catalogo/posse corrigem atualizacoes
  legadas por QuerySet.update que nao disparam signals.
- `home/conquistas.py`: regras permanentes nao sao revogadas pelo reavaliador
  legado; as demais conquistas mantem o comportamento anterior.
- `home/cosmetics.py`: direitos existentes sao lidos sem revarrer personagens
  por moldura. O seletor recebe `unlock_hint` a partir da regra no catalogo.

A legenda das bloqueadas e `alcance lvl X com um personagem pra liberar`.
Diamante informa `lvl 20 e o patamar Epic Boon`, evitando nivel 21 impossivel
no campo de nivel da ficha. Catalogo e manifesto continuam exigindo escopo e
posse, inclusive no POST e na previa; editar o HTML nao concede direitos.

Ativacao normal: `/site update`, incluindo a migration e os estaticos. O backfill
ocorre nessa migration, sem precisar de comando manual adicional. Esta entrega
nao executa a migration nem escreve no banco de producao diretamente.

## Renderizacao e arte

`rank-<rank>-v3.png` preserva a direcao cartunesca e usa transparencia verdadeira
nas duas aberturas. A arte Obsidiana foi harmonizada com dobradicas, borda de
viseira, bochechas e queixo correspondentes nas duas variacoes. Viseiras muito
estreitas foram ampliadas. Os originais v2 permanecem preservados.

Manifestos `moldura-elo-*.json` usam o renderer generico:

- `sprite: open`, `motion: none`: moldura aberta estatica.
- `sprite: closed`, `motion: helmet`: quatro partes da armadura fechada
  (testa, laterais e queixo) se afastam, revelando a aberta por baixo.

O movimento usa transformacoes e opacidade por cerca de meio segundo, reverte
ao sair e funciona com hover, toque mantido e foco natural dentro do avatar.
Com movimento reduzido, a troca e imediata, sem deslocamento das pecas.
O campo de catalogo `animado` permanece falso: ele identifica efeitos continuos
de colecoes pagas, nao uma transicao curta de hover. O manifesto define a viseira.
Nao reproduz a animacao ou o audio de League of Legends; a referencia fornecida
serve somente como direcao de abertura mecanica da armadura.

Perfil, ficha publica/privada, previa da ficha e card de personagem usam o
mesmo pacote. O card respeita uma moldura equipada; o selo de patente continua
indicando o rank mecanico verdadeiro, mesmo usando uma moldura superior da conta.

## Evidencias

Testes focados de direitos permanentes, rollback no laboratorio real,
retroatividade, migracao, compatibilidade das regras legadas e renderer.
UI local com SQLite descartavel: conta inicial tem somente Obsidiana aberta e
fechada; demais opcoes bloqueadas mostram os requisitos. Conta com Diamante tem
as 14 opcoes. Capturas no AmandaBot em `data/catalog_releases/helmet-*-v3.png`
e `rank-unlock-mobile-v3.png`. Galeria local em `art-review.html`.

Edicoes de arte feitas com image_gen integrada, uma por rank, referencia local
v2: preservar paleta e estilo; recortar a viseira direita em alpha, ampliar a
abertura e retirar olhos pintados; manter par aberto/fechado em duas celulas.
Segunda edicao de Obsidiana: adicionar a esquerda as mesmas dobradicas, queixo
e borda angular da direita, mantendo a abertura de retrato transparente.
