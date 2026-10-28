# Lua Vermelha: manual das camadas v2

## Objetivo

Separar a arte aprovada da Lua Vermelha em elementos independentes para ajustar
a composicao em desktop e celular **sem deformar a lua, os galhos ou os
pingentes**. As nuvens passam a existir como um asset proprio, movendo-se
horizontalmente como vento; nao se anima mais um recorte da imagem inteira
para simular uma camada que nao existe.

Este documento registra a familia de assets e sua origem. Nao cadastra
cosmeticos, define preco, concede inventario nem ativa oferta em producao.

## A referencia original continua preservada

O arquivo aprovado e `home/static/cosmetics/proposal-blood-moon-v1.png`
(2117 x 743). Ele continua sendo a referencia visual e nao deve ser sobrescrito
pelas camadas v2. A arte de moldura `frame-lua-vermelha-v2.png` e outro asset:
nao e o disco lunar e nao foi refeita nesta decomposicao.

A imagem original e achatada: partes da lua, do ceu e dos galhos estao ocultas
por outros elementos. O ImageGen extraiu/reconstruiu as familias a partir dessa
referencia, preenchendo regioes escondidas. Portanto, a nova composicao e uma
**reconstrucao aproximada**, nao uma separacao matematica nem uma replica pixel
a pixel do original aprovado. Textura, luminosidade e silhuetas podem variar;
a aprovacao do original nao equivale automaticamente ao aceite dessa variacao.

Na comparacao, preservar principalmente: lua vermelha na regiao direita,
paleta carvao/carmesim, nuvens pinceladas com bordas avermelhadas, galhos secos,
bronze dos pingentes e area central/esquerda livre para a identidade do perfil.

## As seis familias

Todos os arquivos ficam em `home/static/cosmetics/`.

| Familia | PNG fonte/master | WebP de entrega | Funcao na composicao |
| --- | --- | --- | --- |
| Ceu limpo (`sky`) | `blood-moon-sky-v2.png` | `blood-moon-sky-v2.webp` | Base escura texturizada, sem lua, nuvens, galhos ou pingentes impressos. E a unica camada opaca por desenho. |
| Disco lunar (`disc`) | `blood-moon-disc-v2.png` | `blood-moon-disc-v2.webp` | Lua completa, circular, com crateras e brilho discretos; pode ser reposicionada sem esticar. |
| Nuvens (`clouds`) | `blood-moon-clouds-v2.png` | `blood-moon-clouds-v2.webp` | Banco horizontal de nuvens carvao/carmesim, isolado em alpha. Passa diante da lua como camada real. |
| Galhos laterais (`branches`) | `blood-moon-branches-v2.png` | `blood-moon-branches-v2.webp` | Arvore/galhos angulosos da direita, sem lua e sem os pingentes incorporados. |
| Primeiro plano (`foreground`) | `blood-moon-foreground-v2.png` | `blood-moon-foreground-v2.webp` | Pedras e pequenos ramos na borda inferior; centro baixo e leve para nao esconder texto. |
| Pingentes (`charms`) | `blood-moon-charms-v2.png` | `blood-moon-charms-v2.webp` | Tres crescentes de bronze com correntes finas e vazios transparentes, separados da arvore. |

Os nomes identificam a familia de trabalho v2; a presenca/exportacao dos pares
pode ser conferida no diretorio antes da integracao. Uma mesma imagem de nuvens
pode ser usada por mais de uma camada do manifesto, sem gerar outro master:
seis assets nao obrigam o manifesto a ter exatamente seis entradas.

### PNG para editar, WebP para servir

- Conservar os PNGs como masters; nao substituir a referencia aprovada.
- Usar WebP para entrega leve, preservando os canais de transparencia dos
  overlays. O ceu e intencionalmente opaco; nem todo arquivo precisa ter
  pixels transparentes para fazer parte da composicao.
- Fundo preto ou quadriculado desenhado na imagem nao e transparencia.
  A lua, as nuvens, os galhos, o primeiro plano e os pingentes precisam de
  alpha real nas regioes vazias, inclusive entre as correntes.
- Gerar a entrega WebP a partir do PNG correspondente, sem adicionar elementos,
  deformar ou fundir as familias. Quando o manifesto usar fallback PNG, ele deve
  corresponder a mesma camada e proporcao.
- Nao usar GIF nem exportar um video da composicao. O movimento e aplicado
  pelo renderer a imagens estaticas independentes.

## Como recompor sem deformar

Uma leitura visual do fundo para a frente e:
**ceu -> lua -> nuvens -> galhos -> primeiro plano -> pingentes**.
A ordem efetiva, o encaixe e a intensidade devem seguir o manifesto validado;
essa lista explica a funcao das partes, nao substitui o contrato do engine.

Cada familia conserva sua proporcao intrinseca. Alterar tamanho significa
aumentar ou diminuir o elemento como um todo, nao definir largura e altura
independentes para faze-lo caber. A lua deve continuar redonda. Em telas
estreitas, reposicionar, reduzir ou recortar conscientemente e preferivel
a comprimir horizontalmente o conjunto. A escolha entre cobertura e encaixe
do ceu tambem nao autoriza esticar a imagem.

Nao colocar a imagem original completa atras dessas partes: ela ainda contem
lua, nuvens e adornos impressos, criando duplicacao quando a camada nova se
move. A base da composicao v2 e o `sky` limpo. A imagem aprovada fica preservada
como referencia separada, nao como uma segunda lua escondida no fundo.

### Nuvens: agora uma camada de verdade

O asset `clouds` contem somente as nuvens e suas transparencias, sem lua,
paisagem ou retangulo de ceu. Seu deslocamento horizontal deve ser visivel,
lento e independente da lua e dos galhos. A cena nao deve deslizar inteira.

Ajustes de posicao, escala, intensidade e movimento pertencem aos dados do
tema e precisam funcionar na renderizacao inicial e na troca de previa.
A imagem de banner enviada pelo usuario e o texto do perfil continuam
reservados: ajustar a composicao e sua intensidade, nao apaga-los para
mostrar a arte. Movimento reduzido deve manter uma composicao estatica
legivel; aba oculta e elementos fora de tela seguem as protecoes do renderer.

## Contrato tecnico: referencia, nao um segundo schema

O contrato e generico para camadas de qualquer tema, sem condicao por nome.
A fonte normativa e a versao integrada de
`home/cosmetic_packages.py`, em especial `_position_layer` e `parse_package`.
O manifesto de integracao e `home/static/cosmetics/tema-lua-vermelha.json`.

`placement: {x, y, width}` define centro e largura em porcentagem do banner;
`mobile` aceita os mesmos campos para telas de ate 600 px. Altura vem da
proporcao da imagem, nunca de um esticamento independente. `opacity` vai de
0 a 1. `motion: drift` aceita `motion_params: {distance, duration, delay}`:
distancia em porcentagem da largura da propria camada, duracao em segundos
e atraso inicial negativo. O fade das extremidades evita um salto no loop.
Consultar o parser para limites completos e combinacoes aceitas.
Nao adicionar uma chave arbitraria ao JSON nem um movimento especial por nome
de tema para contornar uma rejeicao do parser.

A validacao do manifesto, o template inicial e o renderer da previa devem
interpretar os mesmos dados. Ter os seis PNGs/WebPs no disco, sozinho, nao
comprova que o novo contrato ja foi integrado ou publicado.

Na previa local `20261027-art-direction.html`, os controles permitem ocultar
cada familia e pausar as nuvens. Para ajustar a composicao, editar SOMENTE o
manifesto e regenerar o snapshot da pagina: `node docs/cosmetics/build-moon-preview.cjs`.
O arquivo gerado `blood-moon-preview-data.js` nao deve ser editado a mao.
O site usa o manifesto pelo parser; o snapshot existe apenas porque uma pagina
aberta por `file://` nao pode buscar o JSON por fetch de modo portavel.

Entrega WebP total: 433.820 bytes (seis assets; as duas camadas de nuvens
reutilizam o mesmo arquivo). Masters PNG: 6.482.940 bytes. Transparencia real
conferida nos cinco overlays. Reconstrucao com ImageGen integrado; conversao
de formato/escala proporcional com Sharp, mantendo os PNGs originais.
Testes focados do parser, HTML e movimento passaram; smoke da composicao
em 1280/390 confirmou sete camadas, nenhuma imagem quebrada, centro legivel,
pausa, controle por familia e reducao de movimento. Nao comprova deploy.

## Conferencia rapida para o PO

1. Compare a composicao com a referencia aprovada: identidade e clima similares,
   sem exigir uma equivalencia pixel a pixel inexistente.
2. Observe a lua e as correntes em desktop e celular: sem achatamento,
   esticamento, corte involuntario da lua ou pingentes soltos.
3. Aguarde o movimento: as nuvens devem atravessar a frente da lua enquanto o
   ceu e a lua nao viram uma imagem duplicada deslizando inteira.
4. Confira os vazios: sem retangulos pretos ou quadriculados nas camadas
   transparentes, sem apagar foto, banner proprio ou texto.
5. Ative movimento reduzido e confira a composicao parada; retornar de aba
   oculta nao deve criar camadas extras nem exigir novo salvamento.
6. Distingua arte de obtencao: esta preparacao nao publica, vende ou desbloqueia
   a Lua Vermelha. Cadastro, direitos e aprovacao comercial sao outro fluxo.

Esses itens sao um roteiro de aceite, nao uma declaracao de que todas as
conferencias foram realizadas por este documento.

## Registro de prompts por familia

Origem: seis execucoes ImageGen concluidas no turno
`01a18068-72b0-7020-9fea-e1e9e87ff3a7` do chat principal.
Abaixo estao os prompts enviados a cada execucao, preservados
em ingles. Nao sao prompts retroativamente inventados nem logs de conversao
WebP. Cada execucao recebeu a arte aprovada como referencia.
Os PNGs gerados foram destinados aos masters nomeados acima; os WebPs sao
derivados de entrega, nao seis novas geracoes. Uma repeticao do mesmo prompt
nao garante a mesma imagem.

### 1. Ceu limpo / sky

Registro ImageGen: `exec-c2a008c7-2c83-48b1-b5f9-c82a020d533e`; saida PNG corresponde ao master da tabela.

```text
EDIT supplied Blood Moon artwork into its CLEAN BACKGROUND PLATE for layered animation. Remove ALL foreground elements: remove moon completely, all clouds completely, branches/twigs, rocks, bronze chains/crescents completely. Reconstruct only its very dark charcoal painted sky texture across the ENTIRE wide landscape frame, matching the subtle brushed cloudy charcoal texture in the left empty area of the reference. Nearly black with very subtle deep burgundy on far right. No visible cloud forms, gradients, objects, highlights, horizon, stars, moon or lettering. Broad empty subtly textured deep charcoal background, opaque. Do not make whole original composition again: this is ONLY the clean neutral background layer.
```

### 2. Disco lunar / disc

Registro ImageGen: `exec-90861a93-5a61-4e02-8326-f5f3d7d663b1`; saida PNG corresponde ao master da tabela.

```text
EDIT TARGET reference approved Blood Moon banner. Extract/reconstruct ONLY the single complete round CRIMSON MOON visible at upper right into an isolated square sprite on TRUE TRANSPARENT background. Preserve its exact painted crater design and palette, cartoon/cel-shaded hand-painted texture, sharp circular silhouette, subtle red outer glow only. Reconstruct areas hidden by branches/clouds. Moon occupies 86% of square, centered. Absolutely NO branches, charms, clouds, sky, scenery, stars, text or border. This asset will be positioned independently at natural aspect ratio over a separate background. Preserve style and identity of reference, no realistic photography.
```

### 3. Nuvens / clouds

Registro ImageGen: `exec-22dda8ba-5b48-465f-801a-bbebc0763959`; saida PNG corresponde ao master da tabela.

```text
EDIT TARGET: supplied approved Blood Moon artwork. Extract/reconstruct ONLY the beautiful dark crimson/charcoal wind-swept CLOUDS from this exact picture into a standalone wide horizontal cloud-bank sprite with TRUE TRANSPARENT ALPHA BACKGROUND. Keep the SAME flat-brushed painterly cel-shaded style, angular cloud silhouettes, subtle red rim lighting, dark grey and muted red interiors. NO moon, NO branches, NO charms, NO land, NO opaque sky/background, NO fog rectangle, NO white edges, NO text. Make a wide dispersed cloud bank, isolated floating across the middle of a wide landscape canvas, transparent above and below and softly feathered transparent left/right edges suitable for horizontal drifting over a separate scene. Preserve recognizable shapes from reference rather than generic photoreal smoke. This is one independent layer, NOT a mockup or assembled banner.
```

### 4. Galhos laterais / branches

Registro ImageGen: `exec-abbbaf55-8204-47f2-afe5-02df350c48d5`; saida PNG corresponde ao master da tabela.

```text
EDIT TARGET supplied approved Blood Moon scene. Extract ONLY the jagged leafless dark branches on its FAR RIGHT EDGE into an independent narrow vertical foreground sprite on TRUE TRANSPARENT background. SAME painterly cel-shaded flat-brushed dark charcoal bark, faint crimson edges. Trunk touches right canvas edge, sparse angular small branches reach left with large transparent gaps. Match exact branch language of original, do not invent forest. NO moon, NO clouds, NO bronze ornaments or chains, NO terrain or rocks, NO black background. Everything except branches must have actual transparent alpha. A clean reusable independent layer, portrait canvas.
```

### 5. Primeiro plano / foreground

Registro ImageGen: `exec-c95bd59c-1037-4d10-9a15-5c97dc0df837`; saida PNG corresponde ao master da tabela.

```text
EDIT supplied Blood Moon art. Extract/reconstruct ONLY its low foreground of black angular twigs and red-lit rocks along BOTTOM edge into a separate very wide shallow landscape sprite, true TRANSPARENT above. Match original flat-brushed painterly dark charcoal/crimson cel-shaded style. Thin silhouette ridge hugs bottom, somewhat taller at extreme left/right corners, center almost empty: no thick wall. Delicate thorny leafless twigs at corners. NO right tall tree, NO pendants, NO clouds, NO moon, NO sky, no text. Actual alpha transparent gaps and upper 75% of canvas, not black background. This is a foreground independent layer for responsive composition.
```

### 6. Pingentes / charms

Registro ImageGen: `exec-0e6ce067-3596-44a7-947e-5f2211d429b5`; saida PNG corresponde ao master da tabela.

```text
EDIT supplied Blood Moon artwork. Extract/reconstruct ONLY the three warm BRONZE CRESCENT MOON HANGING CHARMS from the far right into ONE independent narrow vertical ornament layer on TRUE TRANSPARENT background. Preserve elegant thin chains, slim bronze crescents and tiny pendant leaves/geometric drops, warm copper brushed cel-shaded illustrated style exactly as original. One large crescent high, two smaller lower, lightly staggered. They hang from invisible supports. NO tree or branches, NO moon disc, NO clouds, NO scenery, NO background, NO border, NO lettering. Complete transparent gaps between all fine chains. This sprite will be layered on top of a separately drawn tree.
```

