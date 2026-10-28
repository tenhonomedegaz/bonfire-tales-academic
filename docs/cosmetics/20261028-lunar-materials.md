# Tres luas: identidade por material e fechamento do lote

## Revisao atual: irmas da Lua de Sangue

PO considerou a Sangue harmoniosa, mas Negra/Cristal pouco coesas. Duas
edicoes pelo image_gen integrado usam DIRETAMENTE a Sangue v5 como alvo de
referencia para conservar composicao e peso visual. Sem alterar a Sangue.

Prompts: preservar aro fino, curvas elegantes, meias-luas laterais, elos
delicados e joias pequenas superior/inferior, abertura e proporcao originais.
Negra: obsidiana esguia com poucos lascados, verde profundo nas insercoes,
elos finos escuros e pequenas pecas amarelas; evitar aro de entulho/correntes
grossas. Cristal: prata fria, branco leitoso/azulado translucido e poucas
facetas amplas; evitar coroa de gelo, perolas agrupadas e gemas excessivas.
Ambas transparentes dentro/fora, sem glow sobre a foto, sem galhos/textos.

Arquivos novos: `avatar-black-moon-v6.png/.webp` e
`avatar-crystal-moon-v6.png/.webp`. Sangue continua v5. Masters copiados sem
retoques, WebP proporcional640; todos os retratos agora usam centro50/50 e
diametro70 no manifesto. Banners, nuvens, regras, banco e animacoes de rank
nao mudam. Arte proposta para avaliacao visual, nao aceite presumido do PO.
Capturas: `AmandaBot/data/catalog_releases/lunar-siblings-v6/`.

## Ajuste posterior: fonte original preservada na v5

O PO aprovou a direcao artistica, mas apontou diferenca de proporcoes/detalhes
na moldura aplicada em relacao a imagem de referencia. Causa: a segunda
passagem de ImageGen da v4 nao era uma calibracao neutra; redesenhou partes.
Nao foi identificado esticamento de CSS no preview quadrado.

`avatar-*-moon-v5.png` restaura os masters da primeira geracao, byte a byte.
Entrega WebP mantem proporcao quadrada, sem recorte/retocagem. Foto circular
centralizada com diametros 70/70/64% conforme o desenho. Pingentes originais
podem se sobrepor ao contorno da foto; nao sao cortados para impor furo novo.
Nenhuma nova geracao de imagem, alteracao de engine ou mudanca nos temas.

A previa passa a mostrar tambem a arte original sem retrato, na mesma escala
da moldura de 120px. Teste verifica hashes dos PNGs, proporcoes intrinseca e
aplicada, object-fit contain, referencia sem retrato e calibracao em 4 larguras.
Capturas: `AmandaBot/data/catalog_releases/lunar-original-v5/`.
O restante deste documento registra a etapa v4, agora substituida nos manifestos.
A suspensao solicitada na etapa v4 ja foi atendida; este ajuste nao a repete.

## Pedido e limites

Substituir os aneis com pingentes da v3 por estruturas proprias de cada lua.
Sem galhos, sem copiar a mesma moldura e apenas trocar a cor. Preservar foto
circular, banner escolhido pelo usuario e leitura generica de manifestos.
Nao alterar animacoes de rank, precos, elegibilidade, inventarios ou banco.

## Artes entregues

- Sangue: metal dourado/bronze, esmalte vermelho, meias-luas elegantes,
  elos ovais/losangos e rubis.
- Negra: pedra preta lascada, correntes escuras, gemas verdes e pequenos
  detalhes amarelos/osseos inspirados nos pingentes existentes.
- Cristal: branco/azulado facetado, meias-luas polidas, cristais e elos
  geometricos; leitura mais luminosa e eterea.

Arquivos: `home/static/cosmetics/avatar-{blood,black,crystal}-moon-v4.png`
e `.webp`. Gerados pelo image_gen integrado, com transparencia real.
Os tres pingentes existentes foram referencias de material/forma, nao alvos
de substituicao. As versoes anteriores continuam preservadas.

### Prompts utilizados

Base: frame de avatar para comunidade de jogo, quadrado, frontal, circular,
furo central transparente, exterior transparente, estilo cartoon pintado,
ornamentos moderados e formas legiveis a 120px; sem texto, rosto, galhos ou
fundo. A estrutura deve representar o material, nao um anel neutro com lua
fotografica colada no topo.

Sangue: ouro/bronze elegante, vermelho carmim, bandas curvas em crescente,
rubis e motivos de elos ovais/losangos como no pingente de referencia.
Negra: pedra obsidiana lascada, ferro preto, veios/gemas verde-musgo,
pequenos detalhes amarelos/osseos, crescentes de pedra e elos pesados.
Cristal: cristal branco/gelo azulado, juntas claras polidas, crescente
perolado e cristais geometricos, sofisticado e etereo, sem coroa de gelo.

Segunda passagem nas tres: preservar material/design e afastar/encurtar
pontas de joias que avancavam sobre o retrato; pedir abertura circular
central. A geracao nao produz geometria vetorial exata: a calibracao do
manifesto considera o resultado real, sem alegar ausencia total de sobreposicao.
O conversor apenas redimensiona/encoda a arte e preserva seu alpha.

## Temas

Discos normalizados por recorte das margens transparentes e encaixe em
640x640, sem deformar. Todos usam opacidade 0,85, largura 17% desktop/34%
mobile e os mesmos centros. Nuvens, cantos separados, pingentes e movimento
horizontal existente continuam. O fundo permanece sendo o banner do usuario.

## Pendencia de codigo tratada

Na loja mundana/magica, uma resposta atrasada de compra/venda podia atualizar
carteira/inventario de outra ficha apos trocar de personagem. A correcao
vincula a atualizacao visual ao personagem e a geracao de contexto do pedido,
inclusive no trajeto A -> B -> A. Sucesso no servidor continua sendo informado.
Nao ha alteracao de precos, descontos, endpoints ou transacoes do banco.

Arquivos de implementacao e teste:

- `home/static/js/mercado_loja.js`.
- `home/tests_js/market-delayed-trade.test.cjs`.
- Templates `itens_mundanos.html` / `itens_magicos.html`: versao de cache do script.

## Conferencia e proximos passos

- `lunar-materials.test.cjs`: transparencia central, calibracao e opacidade/tamanho iguais.
- `build-moon-preview.cjs --browser-test`: 320/390/768/1280, controles, banners
  proprios, movimento e assets carregados; capturas em
  `AmandaBot/data/catalog_releases/lunar-materials-v4/`.
- Teste focado de resposta atrasada da loja, sem banco/producao.
- Commit/push sao entrega de codigo/assets, nao comprovam deploy.
- Apos `/site update`: conferir em producao autenticada perfil/ficha/miniatura
  e troca de personagem na loja. Nao ativar colecoes apenas para conferir arte.
- Precos/resgate das luas e periodo/elegibilidade da Vigilia seguem pendentes
  de definicao editorial; nao inferir gratuidade ou criar oferta.
- Animacoes de rank ficam para edicao manual pelo PO, conforme combinado.

Encerramento solicitado: suspender o Windows apos salvar e publicar este lote,
sem criar horario de retorno. Jarvis/metas nao sao retomados por esta entrega.
