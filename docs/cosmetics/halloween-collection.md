# Vigilia das Lanternas: conjunto ilustrado

## Entrega

Tema, moldura e efeito com a mesma direcao das Tres Luas, mas linguagem de
Halloween: ferro escuro, latao antigo, luz ambar, pequenas aboboras iluminadas
e detalhes espectrais em verde claro. Preview local sem servidor:
`20261029-halloween.html`. Os quatro controles permitem comparar cada slot
independentemente e pausar o movimento. Os dados da demonstracao sao ficticios.

O tema muda as superficies, cores e acabamento dos paineis, com arte raster
transparente aplicada em nove fatias. A moldura tem abertura circular calibrada,
sem deslocamento ou flutuacao do aro. O efeito usa tres camadas independentes:
nevoa discreta em deslocamento lento, lanternas/abobora no canto inferior
esquerdo e lanternas suspensas no direito. A versao revisada adiciona tres
velas flutuantes e uma aparicao periodica descrita abaixo. O banner do jogador
permanece preservado; a sombra temporaria e apenas uma camada de apresentacao.
Movimento desligado por `prefers-reduced-motion`.

## Dados e arquivos

- `home/static/css/components/illustrated-theme-skins.css`: acabamento
  compartilhado por `skin-illustrated`; a paleta nova fica em
  `skin-vigilia-das-lanternas`. Sem novos `if` no motor ou migration.
- `home/static/cosmetics/themes/vigilia-panel-v1.webp`: painel transparente,
  1024x1024, 117940 bytes.
- `home/static/cosmetics/frame-vigilia-v3.webp`: moldura, 640x640, 82608 bytes.
- `home/static/cosmetics/vigilia-foreground-left-v1.webp`: 800x400, 67078 bytes.
- `home/static/cosmetics/vigilia-lanterns-right-v1.webp`: 360x540, 29930 bytes.
- `home/static/cosmetics/moldura-vigilia-das-lanternas.json`: mesmo slug,
  nova arte e abertura em 50%/50%, diametro 70%; sem animar o aro inteiro.
- `home/static/cosmetics/efeito-vigilia-das-lanternas.json`: mesmo slug,
  overlay transparente com posicao/pivo/mobile, usando o renderizador atual.
- `halloween-catalog.json`: NOVO tema inativo/manual e referencias dos dois
  itens existentes. Nao e backup, fixture ou importacao pronta para restaurar.
- `build-halloween-preview.cjs`: gera `halloween-preview-data.js` lendo os
  manifestos reais. Executar novamente apos alterar camadas. Nao acessa bancos.
- `20261029-halloween.{html,js}`: preview com CSS e renderizador reais;
  layout simplificado, sem substituir a conferencia autenticada apos deploy.

As artes antigas permanecem no repositorio para rollback. A nevoa reaproveita
o asset de nuvens negras ja existente; o restante sao novas imagens RGBA.
O renderer, os modelos e as regras de posse nao foram alterados neste rework.

## Publicacao e acesso

Nao houve escrita em banco, ativacao publica ou concessao de inventario.
Preservar as PKs e posses dos itens existentes, inclusive suspensoes. Durante
QA, manter o acesso ja restrito aos administradores de teste. Elegibilidade,
periodo e eventual resgate publico do evento continuam pendentes de decisao;
nao inferir que todo usuario recebe o conjunto por existir no catalogo.

Depois do deploy dos estaticos, atualizar somente `asset_url` da moldura para
`/static/cosmetics/frame-vigilia-v3.webp` onde necessario; o manifesto ja usa
essa arte. Criar o tema via admin/API com os campos do JSON e conferir antes
se o slug existe. A ativacao e concessao do tema novo devem ser individuais
no QA. Nao trocar tipo/PK dos efeitos por tema, nem sobrescrever selecoes.

Os temas das Tres Luas ja receberam aprovacao visual; o conjunto de Halloween
e uma nova proposta para avaliacao do PO antes de liberacao ampla.

## Validacao focada

`home/test_theme_skin_classes.py` verifica os catalogos e os manifestos nos
dois escopos, incluindo abertura e independencia dos slots. O validador de
pacotes existente confere arquivos e schema, sem acesso a producao.
Evidencias visuais/amostras de tamanho em `../qa/20261029-cosmetic-collections/`.
Nao repetir a suite geral nem recriar a fixture legada ausente para este
ajuste visual; a limitacao anterior esta documentada em `lunar-themes.md`.

## Prompts e ferramenta

Usado ImageGen integrado, nao CLI. Quatro assets, um por chamada; referencias:
moldura antiga de Halloween, Sangue v5 para escala/elegancia e a nova moldura
de Halloween para manter os mesmos materiais. Prompts finais resumidos:

1. Moldura RGBA circular: abertura centrada 70%, aro fino de ferro/latao,
   duas pequenas lanternas, abobora inferior, sem galhos ou grandes asas.
2. Painel RGBA quadrado para nove fatias: cantos fixos com lanterna/abobora,
   arestas discretas pintadas, centro 82% livre, sem padrao vetorial.
3. Primeiro plano inferior esquerdo: cluster baixo de abobora e lanterna,
   poucas folhas, nevoa local transparente, restante vazio, sem cenario.
4. Ornamento direito: duas lanternas em correntes com alturas diferentes,
   luz ambar e jade espectral, suporte de ferro pequeno e fundo transparente.

Conversao posterior somente de dimensoes/formato para WebP com alpha.

## Aparicao e velas: revisao do efeito

O PO considerou a versao inicial pouco perceptivel. O manifesto agora tem
sete camadas: as tres originais (lanternas direitas estaticas), tres copias
de uma vela leve com flutuacao/pulso e o rosto de jack-o-lantern.

O ciclo dura 18s, com quase metade do tempo sem o rosto. Escurece gradualmente,
mostra o rosto de frente, olha para a esquerda, para a direita, volta ao
centro e desaparece sem flash. A sombra chega a aproximadamente 78% e fica
restrita ao banner; nao cobre nomes, controles ou toda a pagina.

### Assets novos e prompts

ImageGen integrado, dois assets RGBA adicionais, salvos/otimizados em:

- `home/static/cosmetics/vigilia-jack-gaze-v1.webp`: atlas horizontal 1536x512,
  tres poses de 512x512, 134574 bytes. Prompt: uma faixa 3:1 com tres celulas
  quadradas iguais, somente olhos angulares de fogo ambar com pupilas finas
  e sorriso entalhado; sem corpo de abobora, nariz, cenario ou fundo; centro,
  escala e boca alinhados entre celulas; pupilas de frente/esquerda/direita;
  pintura cartoon limpa e brilho restrito as formas, sem texto.
- `home/static/cosmetics/vigilia-floating-candle-v1.webp`: vela RGBA 180x270,
  8708 bytes, reutilizada tres vezes com escalas e posicoes distintas. Prompt:
  uma vela esguia de cera marfim com gotas, pequeno pe de latao, chama ambar
  com borda espectral jade e poucos pontos de brasa; levitante, silhueta
  legivel, pintura cartoon igual as lanternas; sem mao, pedestal ou cenario,
  exterior transparente.

### Contrato generico, sem if por cosmetico

`sequence` e um campo opcional do manifesto, validado em
`home/cosmetic_packages.py` e consumido por `renderer.js`. So aceita atlas
horizontal em camadas posicionadas de banner, com `motion: none` ou `float` e sprite
completo. Nao conflita com os sprites de elmo e nao aceita codigo ou CSS.

- `columns`: inteiro de 2 a 8.
- `duration`: segundos de 1 a 120; `delay`: segundos de -120 a 0.
- `backdrop`: intensidade de 0 a 0.85.
- `frames`: 4 a 24 estados, cada um com `at` (0 a 1), `frame` (indice inteiro)
  e `opacity` (0 a 1). Tempos estritamente crescentes, com extremos 0 e 1.
  `shift` opcional (-25 a 25%) calibra o alinhamento horizontal de cada celula.

O renderer usa Web Animations para sincronizar opacidade, celula do atlas e
sombra, com os tempos definidos somente nos dados. A interpolacao das celulas
e discreta, enquanto a aparicao/sombra faz fade. Pausa quando a aba esta oculta
ou o banner sai da tela, cancela animacoes de camadas removidas e remove a
sombra se o asset do rosto falhar. Com reducao de movimento, rosto e sombra
ficam desativados, sem desabilitar as lanternas/velas estaticas.

O partial compartilhado `_cosmetic_preview.html` emite os dados JSON escapados;
o caminho renderizado no servidor e o caminho da previa usam a mesma rotina.
CSS compartilhado v10 e renderer v9 evitam o cache da versao anterior.

### Evidencias desta revisao

- 17 testes focados passaram (schema, rejeicoes, partial, manifestos e catalogo).
- `home/js_tests/cosmetic_sequences.e2e.cjs` compara cinco fases em 390/1440px,
  valida a celula de cada olhar, fade e sombra sincronizados, paridade com HTML
  real do servidor, pausa fora da tela/aba oculta e reducao de movimento.
- Tambem valida que falha no asset nao deixa o banner escurecido sem rosto.
- A regressao existente de layout passou: proporcoes desktop/mobile, camadas
  acima do banner proprio, pivos, pausa, reducao de movimento e seis superficies
  de perfil/ficha, com renderizacao pelo servidor e cliente.
- Capturas das poses e resultado em `../qa/20261029-halloween-apparition/`.

## Refinamento: velas simples e sete poses

A vela detalhada original foi substituida por tres desenhos em poucos tons:
alta de marfim, baixa/larga verde-salvia e media/torta rosa-ameixa. Cada uma
tem quatro quadros de chama, com corpo visualmente estavel e uma chama simples
que se inclina para os lados. Ritmos de 1.6, 2 e 2.4 segundos, com fases e
periodos de flutuacao diferentes. O brilho nao e uma fotografia estatica de
fogo. A calibracao `shift` no manifesto corrige o espaco transparente desigual
das celulas, sem alterar ou redesenhar a arte por codigo.

O jack-o-lantern passa de tres para sete poses: extremo esquerdo, medio
esquerdo, leve esquerdo, centro, leve direito, medio direito e extremo direito.
O ciclo de 18s tem quadros intermediarios em cada deslocamento e conserva
o fade, a sombra sincronizada e o periodo sem rosto. O atlas preserva sua
proporcao intrinseca, incluindo margens transparentes; nao foi esticado para
simular celulas quadradas.

Assets ImageGen integrado novos (antigos mantidos para rollback):

- `vigilia-jack-gaze-v2.webp`: 2240x747, sete celulas, 202954 bytes.
- `vigilia-candle-ivory-v2.webp`: 960x320, quatro celulas, 43452 bytes.
- `vigilia-candle-sage-v2.webp`: 960x320, quatro celulas, 34052 bytes.
- `vigilia-candle-plum-v2.webp`: 960x320, quatro celulas, 43970 bytes.

Todos ficam em `home/static/cosmetics/`. Prompts: atlas de sete poses usando
o rosto v1 como referencia, preservando boca/olhos e movendo so as pupilas;
atlas de quatro quadros por vela com pintura cartoon de 2-3 tons, sem metais,
filigranas ou fogo realista, variando apenas a chama. A vela marfim serviu
como referencia de estilo para as duas silhuetas seguintes.

O contrato generico aceita agora sequencias curtas e flutuacao independente
do atlas. Sem movimento, as velas continuam visiveis e estaticas; somente a
aparicao e sua sombra sao desativadas. CSS v11, renderer v10, dados da previa
v3. Mesmo slug, PKs, acesso, tema e moldura; nenhuma escrita em banco.

Conferencia: 17 testes focados; as sete poses e as tres animacoes de chama
conferidas no navegador, em 390/1440px, com HTML do servidor e previa dinamica,
pausa fora da tela/aba oculta, fallback e reducao de movimento. Capturas e
resultado estruturado em `../qa/20261029-halloween-refined/`.

## Resultado da conferencia de 29/10

- 9 testes focados passaram: 8 de tokens/catalogo/posse/renderizacao e 1
  percorrendo os manifestos existentes com o validador compartilhado.
- Viewports de 320, 390, 768, 1440 e 1920px sem overflow horizontal.
- 60 combinacoes de painel: 4 skins x 5 larguras (240 a 1600px) x 3 alturas
  (96 a 640px), com cantos de 26px e repeticao das arestas preservados.
- Retratos em 46, 96 e 120px com centro coincidente com o aro (erro medido
  zero em x/y) e proporcao 1:1, nos cinco viewports.
- Camadas carregadas, transparencias RGBA presentes, sem erros JS; slots
  independentes e `prefers-reduced-motion` confirmados.
- Capturas `halloween-1440.png`, `halloween-390.png` e resultado estruturado
  `checks.json` na pasta de evidencias indicada acima.
