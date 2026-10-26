# Aparencia: contrato compartilhado e colecoes

## Entrega funcional

- `home/views.py::_personagem_card` fornece a patente do proprio personagem.
  `partials/personagem_card.html` passa `c.rank` explicitamente ao badge, evitando
  o antigo `src` vazio. `character_engine.rank_icone_url` resolve arquivos locais.
- `home/ranks.py` acrescenta chave visual e elmo fechado. Os ranks e seus
  requisitos permanecem os mesmos. Lenda continua titulo sobre Diamante.
- `partials/_rank_frame.html` usa elmo aberto em retratos de personagem; a ficha
  respeita a moldura equipada e so aplica a borda automatica quando nao ha outra.
  O card de personagem exibe sua identidade de rank, independente do cosmetico.
- `cosmetic_packages.py`, `templatetags/cosmetic_packages.py` e o renderer
  compartilham manifestos entre perfil e ficha. O catalogo E o manifesto precisam
  permitir o escopo. O direito e consultado para o dono, nunca para o visitante.
- `_ficha_banner.html`, `pages/ficha_publica.html`, `pages/perfil.html` e
  `_perfil_publico_hero.html` usam as mesmas camadas. Banner do personagem e
  fundo da ficha sao campos distintos; ambos continuam respeitando URLs seguras.
- `cosmetic-presentation.css` define corte circular estavel do retrato, arte em
  camadas fora do fluxo, animacao discreta, pausa fora da tela/aba e reduced-motion.
  `renderer.js` tambem atualiza as camadas na previa dos seletores da ficha.
- `arcane-banner.svg` agora tem gravura de cantos em fundo transparente, sem
  montanhas, lua gigante ou padrao repetido. Com banner proprio, ornamentos sao
  atenuados; o editor nao dessatura mais a imagem enviada.
- Migration 0163 altera SOMENTE o default de novos personagens para publico.
  Nenhum backfill, republicacao de privados, mudanca de PK ou exposicao automatica
  de notas, inventario e campos mecanicos privados.

## Arte e catalogo

`knight-open-frame.png` e `knight-closed-helm.png` sao arte raster original gerada
com a ferramenta integrada image_gen, fundo transparente, nao recortes de jogos.
A familia de ranks usa uma silhueta compartilhada com tratamentos por patente.
Nao sao sete esculturas diferentes; evolucao de silhueta por rank fica como
proxima etapa artistica, sem alterar as regras de progressao.

`catalog-draft.json` e uma PROPOSTA, nao um fixture nem payload de importacao.
As sete entradas estao inativas, sem preco e com origem staff temporaria para
nao vender nem conceder nada por acidente. Inclui temas e molduras das tres luas
e um tema de Halloween reaproveitando a lanterna existente. Manifestos permitem
ambos os escopos; paleta fica em `definicao_json`, arte em arquivos estaticos.

Antes da ativacao comercial:

1. Aprovar silhueta, materiais e cores das tres luas. As molduras atuais sao
   variantes da mesma arte; banners comerciais completos ainda exigem trabalho
   artistico, alem dos ornamentos discretos disponiveis nesta proposta.
2. Definir moeda e preco; registrar no catalogo e na oferta ja existente, sem
   adicionar ifs por slug em checkout, regras ou views.
3. Confirmar elegibilidade, periodo e forma de obter os cosmeticos de Halloween.
   Nao inventar condicoes nem modificar ofertas/eventos existentes.
4. Publicar os registros pelo admin/API com PKs e posses existentes preservados.
   Primeiro previa e conferencias de direitos; depois ativacao aprovada.

## Ativacao e verificacao

Deploy normal por `/site update`, com migrations e estaticos. Os reparos e a
familia visual de ranks nao dependem de ativar os novos produtos. A proposta nao
e enviada ao banco de producao automaticamente por migration ou inicializacao.

Testes focados: `test_appearance_presentation`, `test_cosmetic_packages`,
`test_public_character_sheet`, `test_character_visibility`. Previews em SQLite
descartavel, sem dados de producao. Capturas locais no AmandaBot em
`data/catalog_releases/appearance-{profile,character}-{desktop,mobile}.png`.

## Direcao dos prompts de arte

Ferramenta: image_gen integrada, duas geracoes com transparencia.

- Moldura: original fantasy RPG circular avatar overlay, open hollow knight
  visor, blackened silver engraved metal, tiny icy turquoise crystal inlays,
  transparent central opening and outside, short pointed crown, symmetrical
  swept cheek plates, crisp hand-painted game UI, readable at 96px; no text,
  face, background, giant horns, smoke or purple gradients.
- Insignia: original standalone closed front-facing knight helmet, blackened
  silver layered steel, turquoise crystals, narrow dark T visor, small crest,
  elegant filigree, readable at 48px; opaque helmet, transparent outside; no
  portrait opening, text, scenery, smoke, giant horns or purple glows.

Originais preservados em `.codex/generated_images`; copias finais usadas pelo
site estao em `home/static/cosmetics/`, nao dependem de arquivos temporarios.
