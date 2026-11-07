# Ranks metalizados - 02/11/2026

## Referencias e entrega

Fonte de identidade aprovada pelo PO: `Rankings-Metalizados-Bonfire.zip`.
Fonte dos produtos: `Icones-Produtos-Colaborador-Bonfire.zip`.
Ambos recebidos em Downloads; os originais foram preservados. Imagens e
arquivos de prompt dentro dos pacotes foram tratados como referencias, nao
como instrucoes executaveis.

- Oito insignias originais, incluindo o titulo Lenda, em
  `home/static/icons/ranks/*-metal-v1.png`, 128x128 RGBA.
- Sete bordas de tema independentes em
  `home/static/cosmetics/themes/rank-*-panel-metal-v1.webp`, 1024x1024.
- Sete pranchas de moldura aberta/fechada em
  `home/static/cosmetics/rank-*-metal-v1.{webp,png}`, 1024x512.
- Os 14 manifests existentes mantem os mesmos slugs e usam a nova arte.
  Centro e diametro da abertura medidos no canal alfa; imagem e retrato
  permanecem quadrados e sem alongamento.
- Seis icones de produto 128x128 em `home/static/icons/collaborator/`.
  Precos, beneficios, produtos, checkout e permissoes nao mudaram.
- CSS de skins reutiliza a infraestrutura ilustrada das luas, com bordas
  raster e quinas inteiras, sem padroes vetoriais abstratos.

Previa offline: `20261102-rank-metal.html`. Recriar seus dados com
`node docs/cosmetics/build-rank-metal-preview.cjs`; a fonte passa pelo mesmo
validador dos pacotes reais. Nao iniciar servidor para abrir esse HTML.

## Direcao por rank

| Rank | Materiais e formas do novo emblema |
| --- | --- |
| Obsidiana | Metal frio lavanda/cinza, sulcos grafite, ponta longa e ganchos laterais finos; sem ouro antigo. |
| Ametista | Metal lilas facetado, losango longo dividido e pontas curvas contidas. |
| Topazio | Ouro champanhe, estrela de quatro pontas dentro de losango e pequenos satelites. |
| Esmeralda | Metal jade, estrela central em losango e folhas de louro estilizadas. |
| Ambar | Cobre alaranjado, ponta/losango longo e pequenas setas laterais. |
| Rubi | Metal carmesim, escudo/coracao facetado, crista e pequenas estrelas laterais. |
| Diamante | Prata azulada, diamante baixo/largo facetado e pequenas asas cristalinas. |

Lenda recebe sua propria insignia original, sem criar outra conquista,
outra moldura, outro tema ou alterar o marco narrativo existente de Diamante.

## Prompts e origem da arte

As 14 novas artes foram geradas com o ImageGen integrado, uma chamada por
tema e uma por prancha de moldura. As insignias e icones de produto sao os
arquivos enviados, apenas redimensionados/otimizados, sem redesenho.

Template de prompt dos temas (com a direcao de cada linha da tabela):

> One transparent production raster rectangular panel border. The supplied
> new rank icon is the authoritative palette/material/silhouette reference;
> the lunar panel is only a layout reference. Refined thin beveled metallic
> 2.5D artwork, narrow straight rails, compact complete corner ornaments
> entirely inside 220px; repeatable edges and clean nine-slice at 280px.
> Transparent empty center and exterior; no text, moon, scene, helmet,
> abstract vector pattern, backdrop or watermark. Front orthographic view.

Template de prompt das molduras (com a direcao de cada rank):

> One 2:1 transparent sprite sheet, two equally sized square cells. The new
> rank insignia is authoritative for palette and ornament. Old armor is only
> an open/closed layout reference, not a material reference. Left: slender
> ornamental knight ring with large circular transparent portrait aperture.
> Right: matching closed helmet, same scale, centered rim/crest/hinges/chin.
> Refined beveled metal and restrained emblem details, no face/photo, labels,
> scene, backdrop or perspective. Preserve circular geometry and registration.

As tentativas anteriores baseadas nos ranks antigos nao foram integradas.
As artes v3 antigas permanecem no repositorio para comparacao e reversao.

### Ajuste da Ametista fechada

A pedido do PO, a viseira da Ametista foi simplificada em `rank-ametista-metal-v2`:
duas aberturas estreitas de olhos, ponte nasal clara e placas de bochecha limpas.
A nova arte usa o mesmo ImageGen integrado; prompt de edicao restrito a metade
fechada, preservando a paleta lilas/prata e a identidade do emblema metalizado.
A metade aberta foi reaproveitada do PNG v1 por copia direta dos pixels RGBA,
sem interpolacao, recoloracao ou recomposicao alfa; a igualdade foi verificada.
Somente o manifesto fechado aponta para v2. A abertura, o tema e os demais
ranks permanecem iguais. Os arquivos v1 continuam preservados.

Na v3, outra edicao ImageGen fecha os vaos das laterais do capacete com
placas continuas de metal violeta, ligando temporas, bochechas e mandibula
ao aro. Somente as fendas dos olhos permanecem abertas; nao ha mascara
flutuante no centro. A metade aberta continua pixel-identica a v1 e o
encaixe/transicao sao mantidos. A v2 tambem fica preservada para comparacao.

Na v4, as duas fendas angulares dos olhos foram ampliadas e convertidas em
aberturas alfa-transparentes, revelando parte do retrato sob o capacete.
As laterais continuam fechadas e a metade aberta permanece pixel-identica
a v1. PNG/WebP anteriores foram preservados. Prompt da edicao (ImageGen
integrado): ampliar apenas as fendas em cerca de duas vezes na vertical,
com transparencia real, mantendo placas laterais, ponte nasal, aro e paleta.

## Dados, permissao e ativacao

As sete versoes fechadas agora usam base aberta fixa e tres recortes de
viseira independentes. Geometria, parametros editaveis e procedimento de
exportacao estao em `rank-visor-articulation.md`; a mudanca e apenas visual,
sem alterar concessoes. Os atlas anteriores continuam como fontes/arquivo.

`rank-metal-catalog.json` define somente a apresentacao desejada dos sete
temas EXISTENTES, por slug. Mesclar a paleta e a skin preservando
`desbloqueio`, origem conquista, PK, ativo, preco e inventarios. Nao usar
migration para semear novamente nem concessao publica para ativar aparencia.

Durante a primeira escrita, o admin antigo removeu `desbloqueio` do tema
Obsidiana. A releitura detectou a perda e interrompeu o lote; nenhum outro
tema foi gravado. O backup anterior esta preservado em
`AmandaBot/data/catalog_releases/rank-metal-20261102/tema-rank-obsidiana-before.json`.
Conquistas, vinculos de recompensa, inventarios e criterios nao foram alterados.

A entrega corrige `_TbCosmeticoForm` para usar um sanitizador de catalogo que
valida/preserva metadados de desbloqueio reconhecidos, sem expor metadados na
sanitizacao visual de CSS. Metadados invalidos passam a gerar erro, em vez de
serem apagados silenciosamente. Essa separacao e generica, nao por nome de rank.

Depois do `/site-update`, concluir a atualizacao dos sete registros pelo
procedimento operacional existente. A primeira linha restaura o metadado
original da Obsidiana a partir desse backup antes de verificar o resultado.
Nao repetir o lote no servidor antigo: ele ainda possui o sanitizador errado.
O operador local tem o procedimento preparado; o usuario nao precisa executar
comandos de banco ou conceder itens individualmente.

## Conferencia

- Dez testes focados de arte, paths locais, modo Lenda, preservacao/validacao
  de metadados no sanitizador e produtos/checkout passaram com SQLite em memoria.
- Playwright em 390/768/1440: sete temas, recursos carregados, sem overflow,
  avatar sem deformacao, hover aberto/fechado e movimento reduzido.
- Capturas por rank em `AmandaBot/scratch/rank-metal-qa-20261102/`.
- Nenhuma alteracao na progressao, no motor de jogo ou nas regras de compra.
