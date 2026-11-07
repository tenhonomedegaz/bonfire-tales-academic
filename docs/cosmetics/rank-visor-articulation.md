# Viseiras articuladas dos sete ranks

## Composicao

Os fechados de Obsidiana, Ametista, Topazio, Esmeralda, Ambar, Rubi e Diamante
usam o proprio pacote aberto como base fixa, pixel-identico. Cada aberta foi
exportada em PNG/WebP quadrado de 512 px, sem o fechado antigo na outra metade
do arquivo. Nao alternam entre dois desenhos completos nem dividem o aro em
quadrantes. Aberta e fechada compartilham o mesmo arquivo base em cache.

Cada fechado possui tres PNGs/WebPs transparentes, no mesmo registro de
512 x 512 pixels: frontal superior com ponte nasal, lateral esquerda e
lateral direita. Sao recortes das artes aprovadas, sem redesenho, recoloracao
ou interpolacao. As fendas originais continuam transparentes, incluindo
as fendas ampliadas da Ametista v4. Artes e atlas anteriores ficam preservados.

Uma mascara da abertura do aro mantem os recortes atras da moldura durante
o recolhimento. Ela fica parada: apenas as placas se movem. O frontal sobe;
as laterais deslizam para lados opostos com pequena rotacao e defasagem.
A opacidade cai depois de iniciado o movimento, sem substituir a arte base.
Ao retirar o ponteiro, a mesma transicao retorna ao fechado.

## Dados Editaveis

- `home/static/cosmetics/moldura-elo-<rank>-fechada.json`: primeira camada
  identica a da aberta; as demais referenciam os tres recortes e a mascara.
- `motion: retract`: comportamento generico do leitor, nao condicao por rank.
- `retract.x` e `retract.y`: deslocamento percentual da prancha inteira.
- `retract.rotate`: rotacao em graus.
- `retract.duration` e `retract.delay`: duracao e atraso em milissegundos.
- `retract_mask`: asset local que delimita a abertura fixa, sem mover o aro.
- `rank-visor-rigs.json`: fontes e juntas de recorte por composicao. Editar
  aqui para mudar a divisao de uma placa, nao no leitor Python/JavaScript.

Para reexportar os recortes: executar `docs/cosmetics/build-rank-visors.py`
com o Python do projeto e Pillow. O processo verifica que a abertura nao
vaza para fora do aro e que nenhum pixel de placa foi perdido/duplicado.
Depois regenerar `rank-metal-preview-data.js` com
`node docs/cosmetics/build-rank-metal-preview.cjs`.

## Leitura E Seguranca

`home/cosmetic_packages.py` valida caminhos, escopo, valores numericos finitos
e limites dos movimentos. O template compartilhado e
`home/static/cosmetics/renderer.js` usam os mesmos dados para perfis, fichas
e previews. `home/static/css/components/cosmetic-presentation.css` implementa
a transicao generica, sem nomes de ranks ou concessoes.

O mecanismo antigo `helmet` permanece apenas para compatibilidade com outros
pacotes. Nenhum dos sete ranks usa mais seus recortes genericos de atlas.
Reducao de movimento usa troca instantanea por opacidade, sem deslocamento.
Hover, toque ativo e foco de teclado usam o mesmo comportamento.

Nao ha alteracao de banco, preco, inventario, conquista ou regra de acesso.
Esta entrega precisa de deploy do novo leitor e dos novos arquivos juntos;
a atualizacao anterior de producao nao inclui esta articulacao.

## Conferencia Focada

- `home/test_cosmetic_retraction.py`: validacao dos dados e template.
- `home/test_rank_metal_presentation.py`: sete composicoes, bases preservadas,
  conservacao dos pixels das placas e equivalencia PNG/WebP sem perdas.
- `home/test_cosmetic_packages.py`: contratos existentes e pacotes distribuidos.
- `home/js_tests/rank_visors.e2e.cjs`: 390/768/1440 px, tamanhos de avatar
  46/80/120 px, aro fixo, tres trajetorias independentes, mascara, reversao,
  foco de teclado e reducao de movimento.
- Preview: `docs/cosmetics/20261102-rank-metal.html`.

Resultado local: 33 testes Python passaram; os 21 pares rank/largura do
Playwright passaram sem erros de pagina ou recursos. Os 28 WebPs adicionais
(21 placas e sete mascaras) somam menos de 1 MB. As sete bases quadradas,
as placas e as mascaras somam menos de 1,8 MB em WebP; a base aberta e
compartilhada por ambas as variacoes, sem duplicar seu download.
