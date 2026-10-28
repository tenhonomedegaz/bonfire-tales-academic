# Tres luas: camadas transparentes e edicao por dados

## O que esta entrega muda

A composicao das tres luas passa a ser formada por **overlays transparentes
sobre a imagem de banner escolhida pelo usuario**. Nenhuma delas deve carregar
um ceu ou uma placa de fundo. O objetivo nao e pintar outra imagem por cima do
banner, mas posicionar lua, nuvens, galhos e adornos independentes, sem deformar.

O primeiro plano da Lua Vermelha deixa de ser uma peca larga unica: sao dois
cantos separados. Assim, mudar a largura do banner aproxima ou afasta as
pecas, sem deslocar um bloco de pedras para o meio da tela.

Este e o manual da nova composicao. O documento
`docs/cosmetics/blood-moon-layers.md` registra a etapa anterior da Lua Vermelha,
que ainda descrevia uma placa de ceu; nao deve ser usado como indicacao de que
esse ceu precisa ser carregado nesta entrega transparente.
Nenhum arquivo anterior deve ser apagado para realizar essa mudanca.

## Direcao visual: somente os fatos fornecidos

- **Lua Vermelha / Lua de Sangue:** referencia aprovada preservada, com os
  mesmos quatro assets v2 de disco, nuvens, galhos e pingentes; o primeiro
  plano ganha dois recortes independentes v3.
- **Lua Negra:** associacao a mortos-vivos e necromancia.
- **Lua de Cristal:** Lua de Sangue purificada apos ritual bem-sucedido;
  luz branca dura e lago cristalino.

Essas frases delimitam o briefing. Este manual nao acrescenta origem de
rituais, datas, lugares, entidades, efeitos mecanicos ou outros fatos de lore.
Os prompts e os ornamentos nao sao fonte de novos fatos sobre o mundo.

A referencia aprovada `home/static/cosmetics/proposal-blood-moon-v1.png`
continua preservada. A geracao de partes independentes e uma aproximacao/
reconstrucao das regioes ocultas, nao uma separacao pixel a pixel. A aprovacao
do original nao dispensa conferir a nova composicao.

## Arquivos: PNG master e WebP de entrega

Diretorio de todas as familias: `home/static/cosmetics/`.
Os pares abaixo foram exportados e integrados nos tres manifestos locais.
Isso nao certifica deploy nem ativacao de cosmeticos. Sao **18 assets utilizados**, com PNG master e
WebP correspondente. As 14 geracoes novas sao os dois cantos vermelhos e
seis elementos de cada familia nova; os quatro vermelhos restantes sao reuso.

### Lua Vermelha

| Elemento | PNG master | WebP de entrega | Origem |
| --- | --- | --- | --- |
| Disco lunar | `blood-moon-disc-v2.png` | `blood-moon-disc-v2.webp` | Reaproveita a familia v2 |
| Nuvens | `blood-moon-clouds-v2.png` | `blood-moon-clouds-v2.webp` | Reaproveita a familia v2 |
| Galhos laterais | `blood-moon-branches-v2.png` | `blood-moon-branches-v2.webp` | Reaproveita a familia v2 |
| Primeiro plano esquerdo | `blood-moon-foreground-left-v3.png` | `blood-moon-foreground-left-v3.webp` | Nova geracao de canto |
| Primeiro plano direito | `blood-moon-foreground-right-v3.png` | `blood-moon-foreground-right-v3.webp` | Nova geracao de canto |
| Pingentes | `blood-moon-charms-v2.png` | `blood-moon-charms-v2.webp` | Reaproveita a familia v2 |

### Lua Negra

| Elemento | PNG master | WebP de entrega |
| --- | --- | --- |
| Disco lunar | `black-moon-disc-v2.png` | `black-moon-disc-v2.webp` |
| Nuvens | `black-moon-clouds-v2.png` | `black-moon-clouds-v2.webp` |
| Galhos laterais | `black-moon-branches-v1.png` | `black-moon-branches-v1.webp` |
| Primeiro plano esquerdo | `black-moon-foreground-left-v1.png` | `black-moon-foreground-left-v1.webp` |
| Primeiro plano direito | `black-moon-foreground-right-v1.png` | `black-moon-foreground-right-v1.webp` |
| Pingentes | `black-moon-charms-v2.png` | `black-moon-charms-v2.webp` |

### Lua de Cristal

| Elemento | PNG master | WebP de entrega |
| --- | --- | --- |
| Disco lunar | `crystal-moon-disc-v1.png` | `crystal-moon-disc-v1.webp` |
| Nuvens | `crystal-moon-clouds-v1.png` | `crystal-moon-clouds-v1.webp` |
| Galhos laterais | `crystal-moon-branches-v1.png` | `crystal-moon-branches-v1.webp` |
| Primeiro plano esquerdo | `crystal-moon-foreground-left-v1.png` | `crystal-moon-foreground-left-v1.webp` |
| Primeiro plano direito | `crystal-moon-foreground-right-v1.png` | `crystal-moon-foreground-right-v1.webp` |
| Pingentes | `crystal-moon-charms-v2.png` | `crystal-moon-charms-v2.webp` |

### Molduras de avatar da mesma familia

Cada par abaixo usa PNG editavel e WebP de entrega. Os manifestos
`moldura-lua-vermelha.json`, `moldura-lua-negra.json` e `moldura-lua-cristal.json`
continuam com os mesmos slugs, escopo `ambos` e leitor compartilhado.

| Moldura | Nome-base PNG/WebP | Centro seguro x/y (%) | Diametro seguro (%) |
| --- | --- | --- | --- |
| Lua Vermelha | `avatar-blood-moon-v3` | 50 / 50 | 70.3125 |
| Lua Negra | `avatar-black-moon-v3` | 50 / 50 | 70.3125 |
| Lua de Cristal | `avatar-crystal-moon-v3` | 50 / 50 | 70.3125 |

As artes v1 tinham abertura irregular: encaixar uma foto circular no menor
vao reduzia demais o retrato e deixava lacunas nas laterais. As v2 usam
geometria vetorial circular, sem galhos nem pingentes invadindo a abertura.
Anel, simbolos simples de fases e a lua original como medalhao principal.
As v3 preservam esse encaixe e acrescentam tres pingentes de meia-lua,
com elos curtos e fechos geometricos, sempre fora da foto. Sem galhos;
ornamentos moderados inspirados nos pingentes do banner.
O centro e exatamente (512,512) no SVG 1024x1024 e o raio livre e 360;
`aperture.diameter = 2 * 360 / 1024 * 100 = 70.3125`.
Portanto, o diametro comum corresponde a uma abertura realmente comum,
nao a um numero copiado entre tres desenhos diferentes.

Fontes editaveis: `avatar-*-moon-v3.svg`; exportacoes PNG/WebP preservam
proporcao quadrada. Gerador: `build-lunar-frames.cjs`, com cores por familia
e as imagens lunares ja aprovadas incorporadas ao SVG. Para regenerar:
`node docs/cosmetics/build-lunar-frames.cjs` (Sharp instalado ou fornecido
por `BONFIRE_SHARP_MODULE`). Nao e necessaria nova geracao por IA para
ajustar raio, espessura ou paleta. O leitor generico e as regras de posse
nao foram alterados; o mesmo ajuste atende perfil, ficha e previa.

Teste `lunar-frame-geometry.test.cjs`: alpha livre no circulo central e
variacao radial de no maximo 2 pixels na abertura a 640px, incluindo
antialiasing. Conferencia de navegador em 320/390/768/1280px: foto redonda,
centrada, sem deformacao ou sobreposicao nos tamanhos 40/46/120px.
As v1 e os ranks foram preservados sem modificacoes.

### Ajuste escuro da Lua Negra e fixacao dos pingentes

A Lua Negra usa disco e nuvens v2 realmente mais escuros, nao reducao de
opacidade que revelaria o banner por baixo. Luminancia media ponderada pelo
alpha dos WebPs: disco 79.55 -> 32.29; nuvens 74.90 -> 22.34. E uma medicao
dos assets, nao uma promessa de contraste em qualquer imagem de usuario.
Vermelha e Cristal mantiveram seus discos e nuvens anteriores.

Os pingentes v1 eram estreitos/compridos (aprox. 0.19 de largura/altura),
enquanto o vermelho tem proporcao proxima de 0.64. As novas pecas reorganizam
tres correntes em larguras maiores. Negra usa elos de ferro preto e crescents
de obsidiana; Cristal conserva prata, quartzo e branco purificado.
Ambos usam `pivot: {x:50,y:0}` e `placement.y:0`, presos pelo topo, nao pelo
centro. Larguras sao especificas da proporcao: Negra 8%/16% desktop/mobile;
Cristal 10%/21%. Sao dados no manifesto, sem condicional no motor por tema.

Prompts exatos das sete novas artes e ferramenta usada:
`20261028-moon-polish-prompts.json`. ImageGen integrado; PNGs preservados,
WebPs proporcionais. Nenhum fundo opaco foi adicionado.

### Regras para nao perder o trabalho aprovado

1. Manter os PNGs como masters e os WebPs como arquivos leves de entrega.
   A conversao preserva o alpha e a proporcao; nao e uma nova composicao.
2. Todos os elementos carregados nesta entrega precisam de transparencia real
   fora da silhueta, incluindo o interior vazio dos galhos e das correntes.
   Fundo preto ou quadriculado desenhado nao e alpha.
3. **Nenhuma camada sky.** O antigo `blood-moon-sky-v2.png` e sua entrega WebP
   permanecem preservados, mas nao sao carregados. Tambem nao carregar o
   composite original como um fundo escondido da nova composicao.
4. O antigo `blood-moon-foreground-v2.png` e sua entrega podem permanecer
   arquivados, mas nao devem aparecer junto dos novos cantos esquerdo/direito.
   Caso contrario, o primeiro plano continua duplicado no meio.
5. Nao esticar largura e altura separadamente. A lua deve continuar circular;
   o arquivo informa sua proporcao, e os dados de apresentacao ajustam escala
   e posicao sem deformar a imagem.
6. Nao exportar GIF/video da cena. Os arquivos sao estaticos; movimento de
   nuvens e adornos pertence ao contrato de apresentacao.

## Como as partes se encaixam

Os tres pacotes estao implementados no DEV. No smoke de 390/1280 px: 21
camadas (sete por tema), 18 assets com alpha real, nenhum sky/composite,
nenhuma imagem quebrada, controles independentes, pausa, banner local sem
upload e texto sem overflow. As caixas dos primeiros planos terminaram
exatamente nos cantos inferiores (desvio medido: 0 px).

As versoes WebP dos temas atuais somam 465.012 bytes na Vermelha, 562.504 na
Negra e 717.290 na Cristal. As molduras somam mais 28.768, 22.250 e 28.256
bytes, respectivamente. PNGs editaveis e referencias anteriores foram preservados.
O recorte de margens transparentes alinha o pivot com a arte, nao com um
espaco vazio. A proporcao natural e mantida. A escolha do layout mobile
considera tambem a largura do proprio banner via container query, inclusive
em miniaturas dentro de uma tela desktop.

Nenhum preco, oferta, regra de elegibilidade, inventario ou banco foi alterado.
Publicacao segue o `/site update` habitual e a conferência curta no destino.

A leitura visual e: **banner do usuario -> disco -> nuvens -> galhos ->
primeiro plano esquerdo/direito -> pingentes**.
A ordem precisa ser confirmada no manifesto efetivo. Uma mesma imagem de
nuvens pode ser repetida em mais de uma entrada com ajustes distintos;
isso nao cria um novo master nem exige fundir as imagens.

As nuvens sao uma camada de pixels propria, com vazios transparentes, e
deslocam-se horizontalmente diante da lua. Nao sao um recorte movel do
composite completo. Nem o banner nem a cena inteira devem deslizar para
simular vento. Movimento reduzido deve preservar uma composicao parada,
legivel e sem tapar nome, foto ou texto.

### Por que separar os dois cantos

Cada PNG de primeiro plano deve ter recorte justo: a base da arte toca a
borda inferior, e a silhueta toca a borda lateral correspondente. Grandes
margens transparentes internas podem produzir um deslocamento aparente,
mesmo quando o wrapper esta ancorado no lugar correto.

A ancora da **caixa de destino** e o ponto de **apoio da propria imagem**
precisam coincidir:

| Peca | placement.x | placement.y | pivot.x | pivot.y | Encaixe |
| --- | --- | --- | --- | --- | --- |
| foreground-left | 0 | 100 | 0 | 100 | Canto inferior esquerdo |
| foreground-right | 100 | 100 | 100 | 100 | Canto inferior direito |

Ajustar a largura de uma peca nao deve descolar sua base do canto. Os mesmos
pivots servem em desktop e celular; os dados de celular ajustam a posicao e
a escala admitidas pelo contrato, mantendo a intencao de ancora. Nao compensar
um PNG com margem excessiva esticando a arte.

## Edicao por dados, sem mudar a regra de obtencao

O agente Nash e responsavel pelo suporte generico no engine.
As fontes normativas sao `home/cosmetic_packages.py` (`parse_package`,
`_position_layer`), o renderer compartilhado e o manifesto integrado de
cada tema. Este manual nao substitui a validacao nem declara uma chave
suportada antes de ela estar integrada.

### overlay no manifesto

`overlay: true` pertence a raiz do pacote. O valor e booleano, nao a string
`"true"`. Identifica a composicao como overlay sobre o banner; nao inclui
um fundo novo e nao cria transparencia em um PNG que ja seja opaco.

Fragmento ilustrativo de raiz, nao um manifesto completo:

```json
{"overlay": true}
```

### placement, mobile e pivot na camada

`placement` posiciona e dimensiona uma camada independente.
`pivot` e opcional e pertence a camada, nao a raiz do pacote.
Use a tabela de cantos acima para os dois primeiros planos. Nao tratar
`placement` e `pivot` como sinonimos: o primeiro escolhe o destino; o
segundo escolhe qual ponto da imagem encosta nesse destino.

Fragmentos ilustrativos de camada, nao objetos completos para colar no pacote:

```json
{"pivot": {"x": 0, "y": 100}}
```

```json
{"pivot": {"x": 100, "y": 100}}
```

Preservar a largura e demais campos efetivos do manifesto ao editar apenas
uma ancora. As configuracoes de `mobile` e de `placement` precisam ser
coerentes; editar os dados de desktop nao prova que o celular esta correto.
Nao criar um bloco mobile.pivot por suposicao: consultar o schema integrado.

### O que ajustar e o que nao inventar

| Ajuste desejado | Onde conferir/editar |
| --- | --- |
| Mover ou reduzir a lua sem achatar | placement da camada e variante mobile, preservando a proporcao do arquivo |
| Recolocar pedras/ramos nos cantos | Arquivo esquerdo/direito correto, placement e pivot da tabela |
| Mudar o vento das nuvens | motion e motion_params aceitos pelo parser, sem animar o composite |
| Ajustar intensidade de um elemento | opacity da propria camada, conforme validacao atual |
| Usar o arquivo leve com fonte preservada | file WebP e fallback PNG da mesma familia, no formato validado |
| Confirmar dimensoes intrinsecas | Metadados reais do asset; nao alterar width/height para esticar |
| Proteger banner, foto e texto | Ordem e limites da composicao, nao um fundo escuro opaco sobre o usuario |

Os valores reais de escala, velocidade, intensidade e as combinacoes aceitas
devem vir do manifesto/contrato integrado pelo Main e Nash. Nao adicionar
novos campos ou limites numericos por suposicao neste manual.

O HTML inicial e a troca de previa precisam usar os mesmos dados validados.
Arquivo presente no diretorio nao comprova integracao, publicacao, elegibilidade
ou posse de cosmetico.

## Registro de prompts das 14 geracoes novas

Referencia de trabalho: turno
`01a18093-2ae7-7332-9ce2-6a28a58fc0a0` do chat principal.
Na leitura usada para este documento, estavam disponiveis os dois
`revisedPrompt` concluidos dos cantos vermelhos, transcritos adiante.
Nao atribuir IDs ou transcricoes literais inventadas as outras doze chamadas
enquanto seus registros nao estiverem disponiveis.

### Briefs por asset

A tabela a seguir e um **resumo editorial/reprodutivel do briefing por asset**,
derivado do pedido e das familias de integracao. Nao e transcricao literal do
ImageGen nem prova de que os 14 exports ja estao prontos. Serve para conferir
se cada saida corresponde ao elemento pedido, sem acrescentar lore.

Regra comum aos 14: preservar o estilo da referencia da familia; asset isolado,
sem fundo, alpha real, sem texto, sem outra camada impressa, PNG master.
Para os cantos, o recorte toca a base e a lateral correta da imagem.

| Chamada/familia | Asset | Brief de separacao/geracao |
| --- | --- | --- |
| 1 | Vermelha / foreground-left-v3 | Extrair somente a metade esquerda do primeiro plano aprovado; recorte justo, pedras/ramos tocando as bordas esquerda e inferior, dissolvendo em alpha para a direita. Nao incluir ceu, nuvem, lua, pingente nem mudar o estilo. |
| 2 | Vermelha / foreground-right-v3 | Extrair somente a metade direita do primeiro plano aprovado; recorte justo, pedras/ramos tocando as bordas direita e inferior, dissolvendo em alpha para a esquerda. Nao incluir ceu, nuvem, lua, pingente nem mudar o estilo. |
| 3 | Negra / disc-v1 | Disco completo da Lua Negra, associado visualmente a necromancia e mortos-vivos. Isolado, circular, fundo alpha; sem cena, galhos, nuvens ou texto. Nao acrescentar historia ou entidades novas. |
| 4 | Negra / clouds-v1 | Somente nuvens da familia Lua Negra, coerentes com a referencia e sua associacao a necromancia/mortos-vivos. Banco horizontal sobre alpha, sem lua ou ceu incorporados; bordas apropriadas para deriva horizontal. |
| 5 | Negra / branches-v1 | Somente galhos laterais da familia Lua Negra, em sprite vertical transparente, com grandes vazios reais. Sem disco lunar, nuvens, pingentes, paisagem ou fundo. |
| 6 | Negra / foreground-left-v1 | Primeiro plano da Lua Negra em canto inferior esquerdo independente, recortado justo, coerente com a mesma familia; vazio no centro, alpha fora da silhueta, sem fundo nem novos fatos de lore. |
| 7 | Negra / foreground-right-v1 | Primeiro plano da Lua Negra em canto inferior direito independente, recortado justo, coerente com a mesma familia; vazio no centro, alpha fora da silhueta, sem fundo nem novos fatos de lore. |
| 8 | Negra / charms-v1 | Somente pingentes/ornamentos da familia Lua Negra sobre alpha, sem galhos, lua, nuvens ou paisagem impressos. Preservar identidade visual da familia, sem atribuir significados canonicos novos aos adornos. |
| 9 | Cristal / disc-v1 | Lua de Sangue purificada apos ritual bem-sucedido: disco lunar isolado com luz branca dura e aspecto cristalino. Fundo alpha, proporcao circular, sem outras camadas ou novos fatos de lore. |
| 10 | Cristal / clouds-v1 | Somente nuvens da familia Lua de Cristal, coerentes com a iluminacao branca dura. Banco horizontal transparente; sem disco, ceu, galhos, lago inteiro ou retangulo opaco. |
| 11 | Cristal / branches-v1 | Somente galhos laterais da familia Lua de Cristal, coerentes com a luz branca dura e a referencia. Recorte vertical sobre alpha, sem lua, nuvens, pingentes ou fundo. |
| 12 | Cristal / foreground-left-v1 | Canto inferior esquerdo da familia Lua de Cristal, evocando o lago cristalino da referencia sob luz branca dura. Elementos de borda sobre alpha, sem transformar o lago em um fundo opaco que apaga o banner. |
| 13 | Cristal / foreground-right-v1 | Canto inferior direito da familia Lua de Cristal, evocando o lago cristalino da referencia sob luz branca dura. Elementos de borda sobre alpha, sem transformar o lago em um fundo opaco que apaga o banner. |
| 14 | Cristal / charms-v1 | Somente pingentes/ornamentos da familia Lua de Cristal, com luz branca dura coerente com a referencia, sobre alpha. Sem arvore, disco, nuvens, paisagem, texto ou narrativa adicional. |

### Registro literal disponivel: Vermelha / foreground-left-v3

ImageGen `exec-aace6e76-9f4f-4b82-83f0-b98108be403b`, status registrado: `completed`.
Campo `revisedPrompt`:

```text
EDIT/extract this approved transparent foreground asset. Return ONLY the LEFT HALF as its own independent BOTTOM LEFT CORNER decoration. Preserve the existing angular charcoal rocks, dark red leaves, delicate thorn branches, identical painterly cel-shaded treatment. Remove the entire right half. Crop away excess transparent space ABOVE and around the remaining artwork; tight crop. The bottom of the rocks MUST touch the canvas bottom edge and the leftmost rocks MUST touch canvas left edge so it can pin correctly to bottom-left of responsive banners. Right side feathers naturally into transparency. NO background, sky, moon, clouds, text, new ornaments or changes of style. Real transparent alpha outside this corner silhouette.
```

### Registro literal disponivel: Vermelha / foreground-right-v3

ImageGen `exec-66cdfad8-7343-45a5-9376-cc2aca8733b4`, status registrado: `completed`.
Campo `revisedPrompt`:

```text
EDIT/extract this approved transparent foreground asset. Return ONLY the RIGHT HALF as its own independent BOTTOM RIGHT CORNER decoration. Preserve existing angular charcoal rocks, dark red leaves, delicate thorn branches, identical painterly cel-shaded treatment. Remove the entire left half. Crop away excess transparent space ABOVE and around remaining artwork; tight crop. Bottom rocks MUST touch canvas bottom edge, rightmost rocks MUST touch canvas right edge so it pins correctly to bottom-right of responsive banners. Left side feathers naturally into transparency. NO background, sky, moon, clouds, text, new ornaments or changes of style. Actual transparent alpha outside corner silhouette.
```

Nao esperar repeticao pixel a pixel ao reutilizar um prompt. Registrar a
referencia visual e preservar o PNG aceito e mais seguro do que tentar
regerar silenciosamente uma arte ja aprovada. Os WebPs de entrega nao contam
como novas chamadas ImageGen.

## Conferencia finita para o PO

1. Com um banner claro e com um escuro, confirmar que nao existe sky nem
   retangulo opaco escondendo a imagem do usuario.
2. Em desktop largo e celular estreito, conferir lua circular, adornos
   proporcionais e centro livre para foto/nome/texto.
3. Confirmar que cada primeiro plano encosta no canto inferior correto e que
   aumentar a largura da tela nao cria um bloco no centro.
4. Observar nuvens reais movendo-se horizontalmente; nao deve haver uma
   segunda lua, arvore ou paisagem deslizando dentro delas.
5. Comparar a Negra com a associacao necromancia/mortos-vivos e a Cristal com
   Lua de Sangue purificada, luz branca dura e lago cristalino, sem novos
   fatos de lore deduzidos da arte.
6. Conferir renderizacao inicial e troca de previa com os mesmos dados;
   movimento reduzido e pausa de aba devem continuar respeitados.

Essa lista e um roteiro de verificacao, nao uma declaracao de testes executados
pelo autor deste documento. Novos manifests/assets e seu deploy ficam com os
responsaveis pela integracao. Nenhuma ativacao de banco, oferta, compra, grant
ou mudanca de direitos decorre deste manual. Jarvis e metas pausadas permanecem
pausados.

