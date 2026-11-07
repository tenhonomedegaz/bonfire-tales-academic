# Pacotes visuais de cosméticos

O catálogo e o inventário continuam em `TbCosmetico`/`TbUsuarioCosmetico`. O pacote
fornece apenas mídia para um cosmético **já elegível e equipado**. A validação de
posse e escopo continua no servidor; o renderer não desbloqueia itens.

## Entrega do artista

Coloque um manifesto `home/static/cosmetics/<tipo>-<valor>.json` e os arquivos de
mídia no mesmo diretório. O nome corresponde ao slug do catálogo (por exemplo,
`moldura-ember-ring`); o perfil guarda `ember-ring`. Formato v1:

```json
{
  "version": 1,
  "slug": "moldura-ember-ring",
  "type": "moldura",
  "scope": "perfil",
  "layers": [
    {
      "slot": "avatar",
      "file": "ember-ring.svg",
      "fallback": "ember-ring.svg",
      "width": 160,
      "height": 160,
      "anchor": "center",
      "motion": "pulse"
    }
  ]
}
```

`type`: `tema`, `moldura`, `efeito` ou `banner_preset`. `scope`: `perfil` ou
`ambos`. Slots: `banner`, `ornament`, `avatar`; âncoras: `left`, `center`,
`right`; movimento: `none`, `float`, `pulse`. A duração e o loop são controlados
pelo renderer; o CSS usa 7 s ou 4 s, com loop contínuo. As dimensões declaram a
proporção da arte (32–4096 px por eixo), mas a camada se ajusta ao componente.
Cada manifesto aceita até oito camadas. Use somente nomes de arquivo planos,
minúsculos e com extensão PNG, WebP, GIF ou SVG. Inclua uma imagem estática em
`fallback` quando a arte principal for animada. Arquivos sem fallback válido,
paths externos/relativos e valores desconhecidos fazem o pacote inteiro cair no
visual CSS existente. O navegador também troca a imagem por `fallback` em caso
de erro de carregamento e a remove se ambos falharem.
O manifesto não pode superar 16 KiB; cada arquivo de arte não pode superar 4 MiB.

SVGs desta entrega são arte original do projeto, carregada como `<img>`. A revisão
editorial deve verificar arquivos externos antes da publicação. Pacotes comuns
não recebem JavaScript nem CSS arbitrário. A borda fica ao redor do avatar, o
banner atrás da mídia personalizada, e o ornamento dentro do banner; todas as
camadas ignoram ponteiro. Movimento para fora da tela e com aba oculta é pausado,
e `prefers-reduced-motion` o desativa.

Para novos cosméticos, cadastre o item no catálogo com seu tipo, escopo e origem
corretos, depois entregue manifesto e arte com o mesmo slug. A publicação de
pacotes via admin/upload exige armazenamento e revisão próprios da frente de
backend; nesta etapa os manifestos são versionados no repositório.

Prévia de referência renderizada no Chrome com a arte entregue:
[desktop](../home/static/cosmetics/previews/cosmetic-desktop.png),
[mobile](../home/static/cosmetics/previews/cosmetic-mobile.png) e
[movimento reduzido](../home/static/cosmetics/previews/cosmetic-reduced.png).
São capturas de um fixture local dos mesmos assets/CSS/renderer; não representam
uma sessão autenticada nem uma publicação no catálogo de produção.
