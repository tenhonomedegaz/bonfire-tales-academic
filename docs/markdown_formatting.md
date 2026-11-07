# Formatação Markdown Bonfire

Este documento registra a sintaxe aceita pelos leitores e editores Markdown do site.

## Base

- Markdown comum: títulos, negrito, itálico, links, listas, tabelas, citações e código.
- Cores por nome: `[color=red]texto[/color]`, `[color=cyan]texto[/color]`, `[color=page]texto[/color]`.
- Cores por hexadecimal: `[color=#ff3366]texto[/color]` ou `[color=#f36]texto[/color]`.

As cores curtas antigas (`0` a `9`, `a` a `f` e códigos `&c`/`&r`) não fazem parte do padrão atual.
- Centralizado:

```md
::center
texto centralizado
::
```

- Bloco clicável/recolhível:

```md
::click Título
Conteúdo interno.
::endclick
```

`::toggle` também funciona como alias de `::click`.

## Opções

```md
::options=talentos
```

Esse bloco vira o widget de opções. Ele fica disponível nos leitores gerais, mas é bloqueado no leitor/editor de crônicas. Regiões mantêm a funcionalidade extra já existente de transformar agrupamentos em botões.

## Imagens

Imagem Markdown normal:

```md
![Descrição](https://site/imagem.png)
```

Imagem com modificadores:

```md
![Descrição](https://site/imagem.png){position:right,length:40%,align:upper,layer:same}
```

Também é aceito o formato sem `!` quando houver modificadores:

```md
[Descrição](https://site/imagem.png){position:right,length:40%}
```

Modificadores úteis:

- `position:left` ou `position:right`: flutua a imagem na lateral do texto.
- `position:inline` ou `position:line`: mantém a imagem na linha.
- `position:absolute`, `position:relative`, `position:static`: aplica posicionamento CSS.
- `length:40%`, `len:40%`, `width:40%`: define largura.
- `height:100%`: define altura.
- `position:center`: centraliza a imagem.
- `break:true`: força quebra de linha antes/depois da imagem.
- `break:false`: mantém a imagem inline.
- `align:upper`, `align:middle`, `align:lower`: alinha a imagem na linha do texto.
- `layer:front`, `layer:same`, `layer:back`: controla a camada visual da imagem.
- CSS seguro adicional: `top`, `bottom`, `left`, `right`, `margin`, `object-fit`, `object-position`, `opacity`, `z-index`, `max-width`, `max-height`.

Exemplo próximo do layout com texto à esquerda e imagem à direita:

```md
Texto alinhado normalmente ao lado da imagem.

![Ranks](https://site/ranks.png){position:right,length:40%,align:upper,layer:same}
```

## Atalhos dos editores

- `Ctrl+B`: negrito.
- `Ctrl+I`: itálico.
- `Ctrl+K`: link.
- ``Ctrl+` ``: código.
- `Ctrl+Alt+C`: cor.
- `Ctrl+Alt+I`: imagem.

No Mac, use `Cmd` no lugar de `Ctrl` quando o navegador aplicar essa convenção.
