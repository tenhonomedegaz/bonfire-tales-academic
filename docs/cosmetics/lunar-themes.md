# Temas das Tres Luas

## Estado

Proposta visual implementada em 28/10/2026 e aprovada pelo PO em 29/10/2026.
Os tres registros foram publicados e conferidos na producao em 01/11/2026
pelos formularios administrativos existentes, sem migration nem concessao.
O catalogo esta em `lunar-themes-catalog.json`, com `ativo: true`, origem
`staff` e liberacao manual por administrador. Inventarios foram preservados.
As molduras e os efeitos aprovados nao foram alterados.

Preview: `20261028-lunar-themes.html`. Abre diretamente como arquivo, sem servidor.
As abas permitem comparar perfil publico, campos do editor e paineis de ficha.
O preview usa as classes e a folha de skin reais, mas dados ficticios e layout
reduzido; nao substitui a conferencia das paginas autenticadas apos publicacao.

## Direcao visual

| Tema | Materiais | Paleta |
| --- | --- | --- |
| Lua Vermelha | metal pintado, esmalte vermelho, pequenas luas | vinho, vermelho, ouro envelhecido |
| Lua Negra | obsidiana, metal escuro, pequenos engastes | grafite, verde espectral, dourado discreto |
| Lua de Cristal | prata pintada, pequenos cristais | branco-prateado, azul cristal, fundo petroleo |

O acabamento vem de tres imagens raster transparentes, nao de desenhos SVG,
gradientes geometricos ou padroes vetoriais. A arte e aplicada por nove fatias:
cantos com tamanho fixo, arestas repetidas sem esticar joias e centro sem fill.
O movimento e somente uma respiracao sutil de luminosidade dos titulos,
desativada por `prefers-reduced-motion`. Nao move texto ou formularios.

As superficies mantem espaco livre para leitura. O banner escolhido continua
independente do tema e dos efeitos. Nos cabecalhos, a borda reserva espaco para
que o banner nao cubra os ornamentos. Cores de sucesso/erro e regras de jogo
nao recebem alteracoes especificas destes temas.

## Contrato e arquivos

- `home/static/css/components/illustrated-theme-skins.css`: skins, paletas e
  acabamento de paineis, editor, ficha, cartoes e miniaturas do catalogo.
- `home/static/cosmetics/themes/*-panel-v1.webp`: 1024 x 1024 RGBA; 141936,
  103790 e 144054 bytes respectivamente para sangue, negra e cristal. Somente
  o asset referenciado pelo tema presente na pagina precisa ser carregado.
- `home/views.py`: `_data_theme_class` preserva tokens CSS validos vindos do
  catalogo junto de `theme-data`; nao tem condicional por lua. Permissoes,
  suspensao de inventario, escopo e sanitizacao de cores continuam no fluxo
  existente. Composicoes antigas conservam compatibilidade.
- `home/static/js/tema_swatch.js`: troca e remove tokens de skin ao selecionar
  outro tema, preservando efeito, fundo e dados do personagem; sincroniza a
  previa autorizada com o editor privado.
- `home/templates/home/includes/tema_swatch_card.html`: a miniatura recebe a
  classe do tema para mostrar tambem o asset, nao so a paleta.
- `home/templates/home/base.html`: carrega a folha compartilhada de skins.
- `home/templates/home/pages/{perfil,ficha_detail}.html`: versao de cache do
  seletor atualizada para 4.
- `home/test_theme_skin_classes.py`: testes de tokens, troca no JS, posse,
  escopos, suspensao, perfil/ficha e previa sem persistencia.

Cada tema sera um NOVO registro de `TbCosmetico`, tipo `tema`, origem `staff`,
escopo `ambos`, com cores em `definicao_json` e sua skin em `css_class`.
Nao e necessario alterar modelos, schema ou criar migration de conteudo.
Nao converter de volta os efeitos 54/55/56, nem reutilizar suas PKs ou posses.

## Publicacao apos avaliacao

1. Visual das tres luas aprovado; preservar a arte durante a publicacao.
2. Publicar o codigo/estaticos pelo fluxo usual do site.
3. Criar os tres registros a partir do catalogo proposto pelo admin ou API
   existente, verificando previamente os slugs; nao executar importacao cega.
4. Ativar e conceder individualmente somente aos administradores de teste.
   O JSON proposto nao e uma fixture de backup ou comando de importacao.
5. Conferir perfil publico/privado, ficha, seletor e banner+efeito em producao.
   Manter liberacao manual por admin para os demais jogadores.

## Evidencias e limites

- 14 testes focados de skins e cartoes do perfil passaram em SQLite descartavel.
- O grupo legado `CartoesDeTemaNaFichaTests` nao conseguiu iniciar porque a
  fixture `home/fixtures/conteudo.json` nao existe nesta copia. Nao foi recriada
  nem substituida por dados de producao. A renderizacao da ficha e o controle
  de escopo estao cobertos pelos testes novos sem essa fixture.
- Seis capturas em `../qa/20261028-lunar-themes/`: desktop 1440 x 1000 e
  celular 390 x 844, nas tres abas. Sem overflow horizontal ou erros JS;
  tres assets com alpha e centro visualmente transparente; modo de movimento
  reduzido respeitado.
- `git diff --check` sem erros de whitespace.
- Cadastro e ativacao conferidos pelos formularios autenticados na producao
  em 01/11/2026. A skin corrigida depende da atualizacao dos estaticos.
- Temas usam cores e skin. Seus manifests sem camadas desativam a midia
  legada; luas, nuvens e pingentes continuam nos efeitos independentes.

## Origem da arte

Gerada por ImageGen com as molduras aprovadas como referencia de material,
sem alterar aquelas molduras. Brief: borda retangular estreita para nove
fatias, centro/exterior transparentes, detalhes lunares pequenos nos cantos,
arestas retas e discretas, sem texto, cena, rosto, galhos ou padrao vetorial.
Vermelha: metal dourado e esmalte carmesim; negra: obsidiana/grafite, verde e
amarelo antigo; cristal: prata, azul claro e pequenos cristais etereos.
Otimizacao posterior somente de tamanho/formato, preservando alpha.

## Adaptabilidade e reutilizacao

O acabamento usa `skin-illustrated` mais a classe de paleta escolhida. A mesma
folha atende as tres luas e a Vigilia das Lanternas, sem mudar o renderizador
ou criar condicionais por item. `--lunar-*` e o namespace interno original de
material, preservado por compatibilidade; nao representa exclusividade lunar.
Os tokens completos estao nos JSONs de catalogo; usar ambos, nao so a paleta.

Cantos usam corte de 280px no asset e tamanho de 40px na tela, preservando
os pingentes inteiros; a arte das arestas se repete, em vez de esticar.
Isso preserva a proporcao ao variar largura e altura. Conteudo muito extenso
ainda precisa de quebra de linha: a skin permite `overflow-wrap:anywhere`,
nao encolhe a fonte e nao promete legibilidade em caixas arbitrariamente
menores que seus controles. Abaixo de 320px de viewport continua necessario
avaliar o layout da pagina, nao apenas a arte da borda.

Conferencia ampliada e conjunto de Halloween: `halloween-collection.md`.
