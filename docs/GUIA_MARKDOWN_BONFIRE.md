# Guia de Markdown do Bonfire

Este guia documenta as tags aceitas pelos leitores e editores Markdown do site.

## Markdown base

```md
# Titulo principal
## Topico
### Subtopico

**negrito**
*italico*

- bullet
  - sub-bullet

[link](https://exemplo.com)
![texto alternativo](https://exemplo.com/imagem.png)
```

Os leitores usam GFM via `marked`, com quebra de linha simples habilitada (`breaks: true`).

## Cores

```md
[color=red]texto vermelho[/color]
[color=#ff8800]texto com hex[/color]
[color=page]texto na cor da pagina/regiao[/color]
```

Cores predefinidas:

`red`, `blue`, `cyan`, `green`, `yellow`, `gold`, `purple`, `dark-blue`, `dark-green`, `dark-cyan`, `dark-red`, `dark-purple`, `white`, `gray`, `dark-gray`, `black`, `ember`, `flame`, `spark`, `muted`, `page`.

Hex aceito:

`#rgb`, `#rrggbb` ou `#rrggbbaa`.

## Bloco centralizado

```md
::center
Texto centralizado
::
```

## Bloco clicavel/expansivel

```md
::click Titulo do bloco
Conteudo em Markdown.
::endclick
```

Tambem aceita `::toggle`. Em cronicas, `::options` fica bloqueado por nao fazer sentido nessa pagina.

## Widget de opcoes

```md
::options=tipo-da-opcao
```

Renderiza automaticamente opcoes cadastradas do tipo informado. Use em leitores onde opcoes fazem sentido.

## Imagens com modificadores

Formato:

```md
![nome da imagem](https://exemplo.com/imagem.png){position:right,length:40%}
```

Tambem funciona sem `!`:

```md
[nome da imagem](https://exemplo.com/imagem.png){position:right,length:40%}
```

Os modificadores tambem podem ficar na linha seguinte, util quando o editor estiver estreito:

```md
![nome da imagem](https://exemplo.com/imagem.png)
{position:right,length:40%}
```

Modificadores úteis:

- `position:right` ou `position:left`: alinha a imagem na direita/esquerda e deixa o texto contornar.
- `position:center`: centraliza a imagem. Ideal para imagem em destaque, sem texto contornando.
- `position:inline`: coloca a imagem na linha do texto.
- `position:absolute`, `position:relative`, `position:static`: aplica position CSS. Com `break:true`, `absolute` e coordenadas (`top`, `left`, etc.) sao ignorados para a imagem nao cobrir o texto.
- `length:40%`: atalho para `width:40%`.
- `width:40%`, `height:100%`, `max-width:420px`.
- `break:true`: coloca a imagem em um bloco proprio, sem ser arrastada para dentro do paragrafo. A imagem participa do layout e o texto quebra antes/depois do bloco.
- `break:false`: permite imagem inline.
- `align:upper-margin`, `align:top`, `align:middle`, `align:lower-margin`: alinhamento vertical para imagem inline.
- `layer:front`, `layer:same`, `layer:back`: camada visual relativa ao texto.
- `zindex:3`: atalho para `z-index:3`.
- `margin`, `margin-left`, `margin-right`, `bottom`, `top`, `left`, `right`, `opacity`.

Exemplo recomendado para imagem lateral como no layout de texto + imagem:

```md
Texto do bloco na esquerda.

![Ranks](https://exemplo.com/ranks.png){position:right,length:40%}
```

## Atalhos dos editores

- `Ctrl+B`: negrito.
- `Ctrl+I`: italico.
- `Ctrl+K`: link.
- `Ctrl+Alt+I`: imagem.
- Atalho de cor: insere `[color=][/color]` sem escolher a cor. O seletor visual fica no botao Cor.

## Collections e bancos

O adaptador legado tem dois grupos:

- Banco do site: collections configuradas em `SITE_POSTGRES_TABLES`.
- Banco original do bot: collections configuradas em `BOT_POSTGRES_TABLES`.

As collections nativas do bot nao devem ser renomeadas. O site deve gravar conteudo proprio nas collections do site.
