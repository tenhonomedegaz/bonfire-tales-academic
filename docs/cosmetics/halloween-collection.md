# Vigilia das Lanternas

## Conjunto e direcao

Tema, moldura e efeito independentes, com ferro escuro, latao dourado,
cera marfim e fogo ambar pintado. O acabamento acompanha as lanternas e
ornamentos do conjunto; nao usa velas de estilo minimalista ou plano.

Preview local: `20261029-halloween.html`. Abre sem servidor, com dados
ficticios, CSS e renderizador reais. Os controles permitem desligar cada
slot e o movimento. Nao substitui a conferencia autenticada apos o deploy.

O tema usa paineis raster em nove fatias e a skin compartilhada
`skin-illustrated skin-vigilia-das-lanternas`. A moldura continua circular,
com abertura em 50%/50%, diametro 70%, sem deslocamento do aro inteiro.
Os temas e as molduras aprovados das Tres Luas nao foram redesenhados.

## Efeito do banner

Sete camadas-raiz: nevoa, decoracao inferior esquerda, lanternas direitas
estaticas, tres grupos de velas e a aparicao do jack-o-lantern.

Os grupos tem exatamente uma, duas e tres velas finas, cada qual em suporte
dourado. Corpos e suportes sao imagens fixas: nao trocam de desenho durante
a animacao. Cada chama e uma parte independente, posicionada no pavio.
Os grupos inteiros percorrem um movimento suave horizontal/vertical com
pequena rotacao, em ciclos distintos de 8.2, 10.6 e 12.8 segundos.

O fogo usa **12 desenhos reais**, organizados em atlas 4x3. As seis chamas
reutilizam a mesma textura em fases/ciclos diferentes (1.15 a 1.59 segundos).
O corpo da vela nao varia de largura ou altura ao trocar a pose do fogo.

O jack tem sorriso e contornos fixos, com pupilas separadas. O olhar usa
**24 poses de controle e interpolacao continua**, em vez de 24 desenhos
completos que poderiam deformar a boca entre quadros. Ha pelo menos 16
posicoes horizontais distintas e poses de transicao/repouso no ciclo.
Isso permite movimento subpixel entre as poses. Nao sao 24 PNGs distintos.

O ciclo de 18 segundos mantem aparicao/fade/sombra sincronizados. A sombra
temporaria chega a cerca de 78%, restrita ao banner; nao escurece a pagina
inteira, nomes ou controles. O banner escolhido pelo jogador permanece
intacto, atras das camadas transparentes.

## Assets atuais

Todos em `home/static/cosmetics/`, WebP RGBA:

| Arquivo | Tamanho | Uso |
| --- | --- | --- |
| `themes/vigilia-panel-v1.webp` | 1024x1024 | Acabamento de paineis |
| `frame-vigilia-v3.webp` | 640x640 | Moldura de avatar |
| `vigilia-foreground-left-v1.webp` | 800x400 | Decoracao esquerda |
| `vigilia-lanterns-right-v1.webp` | 360x540 | Lanternas direitas |
| `vigilia-candlestick-one-v3.webp` | 400x600 | Uma vela + suporte |
| `vigilia-candlestick-two-v3.webp` | 500x750 | Duas velas + suporte |
| `vigilia-candlestick-three-v3.webp` | 560x840 | Tres velas + suporte |
| `vigilia-flame-twelve-v3.webp` | 1024x768 | Doze poses, cache compartilhado |
| `vigilia-jack-base-v3.webp` | 640x640 | Boca e olhos sem pupilas |
| `vigilia-jack-pupil-v3.webp` | 128x128 | Pupila, reutilizada nos dois olhos |

Artes anteriores preservadas para rollback, mas nao referenciadas pelo
manifesto atual. A nevoa reaproveita `black-moon-clouds-v2` ja existente.

## Dados e fluxo

- `efeito-vigilia-das-lanternas.json`: composicao e tempos atuais; mesmo slug.
- `moldura-vigilia-das-lanternas.json`: moldura aprovada; mesmo slug.
- `halloween-catalog.json`: tema novo inativo/manual e referencias dos itens
  existentes. Nao e backup, fixture ou importacao para restaurar.
- `build-halloween-rigs.cjs`: autoria dos dados numericos de corpos, pavios,
  fases, trajetorias e olhar; nao altera imagens nem acessa banco.
- `build-halloween-preview.cjs`: exporta manifestos e partes recursivamente
  para `halloween-preview-data.js`, permitindo abrir a previa via `file://`.
- `home/cosmetic_packages.py`: valida os campos genericos, sem if por item.
- `home/static/cosmetics/renderer.js`: monta rig, atlas e partes com Web
  Animations; mesmo caminho para HTML do servidor e previa viva.
- `home/templates/home/partials/_cosmetic_preview.html`: JSON escapado de
  sequencias/partes, sem aceitar scripts ou CSS livre nos dados.
- `home/static/css/components/cosmetic-presentation.css`: geometria
  compartilhada, clipping dos atlas e comportamento de acessibilidade.

Depois de ajustar os dados de autoria, executar os dois builders acima,
nessa ordem. Nao sobrescrever manualmente o snapshot gerado da previa.

## Contrato generico

`sequence` aceita `columns` de 1 a 8, `rows` opcional de 1 a 8, duracao de
1 a 120s, atraso de -120 a 0s, `backdrop` de 0 a 0.85 e 4 a 64 estados.
Cada estado exige `at`, `frame` e `opacity`: tempos crescentes de 0 a 1,
indice inteiro dentro do atlas e opacidade de 0 a 1.

Campos opcionais de pose: `shift` horizontal da celula (-25 a 25%), `x/y`
(-100 a 100%), `rotate` (-15 a 15 graus), `scaleX/scaleY` (0.8 a 1.2).
As celulas do atlas trocam discretamente; a pose do viewport interpola.
Valores sao numericos finitos e limitados, nunca codigo de animacao livre.

`parts` permite de uma a seis partes posicionadas, em um unico nivel, sem
novas partes dentro delas. O pai deve ser um rig 1x1; partes tem sombra zero.
Assim fogo acompanha o suporte e pupilas acompanham o rosto, preservando
escala/posicao em diferentes tamanhos. O limite do manifesto e 64KiB.

Pausa fora da tela ou com aba oculta. Com reducao de movimento, corpos e
chamas ficam estaticos; aparicao e sombra ficam ocultas. Falha de um asset
pai cancela suas animacoes e as das partes; falha do rosto remove a sombra.

## Verificacao e fluidez

`home/test_cosmetic_rigs.py`, `home/test_cosmetic_sequences.py` e o validador
existente cobrem schema, limites, HTML escapado e rejeicao de partes profundas.
Foram executados 28 testes focados, sem banco de producao.

`home/js_tests/cosmetic_sequences.e2e.cjs` verifica em 390/1440px: grupos de
1/2/3, seis chamas, todas as 12 celulas, poses do olhar, paridade servidor/cliente,
pausa, reducao de movimento e limpeza de partes quando o pai falha.
Tambem amostra 241 instantes do olhar para medir saltos e verifica que os
suportes mantem a mesma imagem ao mover em ambos os eixos.
Resultados numericos e capturas: `../qa/20261029-halloween-candelabra/`.

Na amostragem de 75ms, o maior passo do olhar foi 5.2084% da largura da
parte da pupila, sem troca da boca ou do contorno do olho. As trajetorias
dos tres suportes variaram em x e y mantendo a imagem do corpo no frame zero.
CSS v12, renderer v11 e dados da previa v4 identificam esta composicao.

## Publicacao e acesso

Sem escrita em banco, novos modelos, migration ou concessao publica.
Preservar PKs, posses e suspensoes dos itens existentes. Durante QA, manter
os administradores de teste; elegibilidade e eventual resgate publico do
evento continuam pendentes de decisao. Nao inferir liberacao pelo catalogo.

Depois do deploy, atualizar `asset_url` da moldura para
`/static/cosmetics/frame-vigilia-v3.webp` somente se ainda apontar para a arte
antiga. Criar/ativar o tema via admin/API, conferindo o slug antes. Nao mudar
tipo ou PK dos efeitos nem sobrescrever selecoes. Assets e codigo nao fazem
automaticamente essas alteracoes de dados.

## Origem e prompts

ImageGen integrado; conversao posterior somente de tamanho/formato com alpha.
Suporte enviado pelo PO e lanternas existentes como referencias de material.
Prompts finais: uma, duas e tres velas marfim MUITO finas, pavios sem fogo,
suportes de latao/ouro antigo em pintura fantasy detalhada, sem cartoon plano;
atlas 4x3 de doze chamas coerentes com raiz fixa em 50%/85%, nucleo branco,
corpo dourado e base azul discreta; jack unico no estilo aprovado, sem pupilas;
pupila escura separada e pontiaguda. Sem cenario, texto ou fundo opaco.
