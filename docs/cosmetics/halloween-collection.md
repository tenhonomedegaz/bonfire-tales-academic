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
esquerdo e lanternas suspensas no direito. Centro livre e banner do jogador
preservado. Movimento desligado por `prefers-reduced-motion`.

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
