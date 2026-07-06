# Arquitetura — Temas Dinâmicos & Studio de Cosméticos (staff)

> Normativo. Decisões do PO (2026-07): temas atuais são genéricos/hardcoded; staff
> precisa de autonomia pra criar **temas, badges e conquistas** próprios (inclusive
> upload de arquivo de estilo); seletor de tema deve mostrar **prévia visual**;
> remover o **sweep de luz** do banner (incomoda); criar **temas basais** mais
> elaborados pra apresentar o produto. NÃO mudar disposição/posição de itens
> (principalmente na ficha); conquistas continuam compactas, sem ícone grande.
> `background_url` continua existindo (será refinado depois).

## 1. Tema como dado (`TbCosmetico.definicao_json`)

Hoje um tema é uma classe CSS hardcoded (`.theme-ember` etc. em perfil.css/ficha.css)
+ vars `--profile-*`/`--sheet-*`. O mecanismo do tema *custom* já prova o caminho:
JSON validado (hex-only) → vars inline. Generalizamos:

- **Novo campo** `TbCosmetico.definicao_json` (dict, só usado por `tipo='tema'`):

  ```json
  {
    "accent":  "#RRGGBB",   // obrigatório (default ember)
    "accent2": "#RRGGBB",
    "surface": "#RRGGBB",
    "deep":    "#RRGGBB",
    "gradiente": true,               // accent vira linear-gradient(accent, accent2)
    "particula": "subir|cair|flutuar|nenhuma",   // default subir
    "vel": "lenta|media|rapida",                 // default media
    "glow": true                                  // halo de acento nos cards
  }
  ```

  Sanitização server-side obrigatória em TODA renderização (mesmo padrão de
  `_sanitize_custom_theme`: só `^#[0-9a-fA-F]{6}$`, enums whitelisted). Nenhuma
  string livre chega a style inline.

- **Novo campo** `TbCosmetico.css_file` (FileField `.css`, upload staff-only via
  admin): escape para temas avançados. Quando o tema equipado tem arquivo, o
  template inclui `<link>` pra ele (servido de MEDIA). Confiança = staff (mesmo
  nível dos campos HTML que o admin já edita). Validar extensão.

- **Renderização** (`_appearance_context`): se o tema escolhido tem
  `definicao_json` não-vazio → emite vars inline (mesmo builder do custom,
  cobre `--profile-*` E `--sheet-*`) + expõe `fx_particula`, `fx_vel` e
  `theme_css_href`. Classes legadas (`theme-ember`…) continuam funcionando
  como fallback; após o backfill (§4) os 5 temas antigos também viram dados.

- **Partícula dirigida por atributo**: o elemento temado (`.public-profile-page`,
  `.ficha`, `.player-card`) ganha `data-fx-particula="…"` e `data-fx-vel="…"`.
  `perfil-fx.css` seleciona por atributo (com fallback nas classes de tema
  legadas). Assim tema novo = zero CSS novo.

- **/jogadores**: cards de outros usuários precisam das vars → o contexto batch
  emite style inline por card quando o dono usa tema-dado.

## 2. Autonomia de conteúdo (studio staff no admin)

- `TbCosmetico.asset_file` (upload de ícone de badge; `asset_url`/glyph continuam;
  efetivo = file > url > emoji > 🏅).
- `TbConquista.icone_file` (idem; efetivo = file > icone_url > 🏆).
- Admin TbCosmetico: fieldset "Tema (dados)" com `definicao_json` + `css_file`;
  form valida a definição com o sanitizador.
- **Wipe do conteúdo demo** (migração de dados): apagar os seeds F2/F3
  (títulos `titulo-veterano-mesas`, `titulo-portador-chama-eterna`; badges
  `badge-matador-dragoes`, `badge-primeira-fogueira`; e as conquistas do seed
  0052), limpando grants e `titulo_equipado`/`badges_destaque` pendurados.
  Badges DERIVADAS (staff/apoiador/mestre-ouro/fundador) ficam — são estado
  computado, não conteúdo.
- Render precisa ser gracioso com cosmético/título deletado (sem 500).

## 3. Seletor com prévia

No editor (perfil e ficha), cada opção de tema vira um **card-swatch**: fundo =
`surface`, barra `accent→accent2`, 3 pontinhos de partícula, nome embaixo;
radio escondido (mesmos names/values — o preview ao vivo existente continua).
Dados vêm de `catalog_options` (que passa a incluir a `definicao` sanitizada).
Mesmo lugar/tamanho aproximado do controle atual — sem reflow do resto.

## 4. Temas basais (seed, provam o sistema)

Backfill dos 5 legados como dados (cores atuais) + 6 novos (origem=livre):

| slug | nome | accent | accent2 | surface | deep | grad | partícula/vel |
|---|---|---|---|---|---|---|---|
| tema-coracao-da-forja | Coração da Forja | #FF7A1A | #FFD166 | #1A0F08 | #0D0806 | sim | subir/rapida |
| tema-abissal | Abissal | #38E1FF | #2563EB | #071722 | #030B12 | sim | flutuar/lenta |
| tema-bosque-ferico | Bosque Feérico | #4ADE80 | #FACC15 | #0B1D12 | #05100A | não | flutuar/media |
| tema-veu-lunar | Véu Lunar | #E2E8F0 | #7DD3FC | #0D1220 | #05070D | não | cair/lenta |
| tema-sangue-e-ouro | Sangue & Ouro | #EF4444 | #F59E0B | #1C0A12 | #10050A | sim | subir/media |
| tema-tempestade-arcana | Tempestade Arcana | #A78BFA | #22D3EE | #140F26 | #0A0716 | sim | flutuar/media |

Backfill legado: ember `#F59E0B/#7C2D12/#1B120F/#0E0A08` subir/media;
arcane `#A78BFA/#06B6D4/#151223/#090914` flutuar/lenta; verdant
`#34D399/#84CC16/#0E1A14/#07110C` subir/lenta; moonlit
`#CBD5E1/#60A5FA/#10151F/#080B10` cair/lenta; bonfire (default)
`#F27007/#D21717/#101012/#09090A` subir/media.

## 5. Remoções

- **Sweep do banner** (`.public-profile-banner::after` + `@keyframes fx-aurora`
  em perfil-fx.css): REMOVER — sempre-ativo, incomoda. O *efeito escolhível*
  `aurora` do catálogo continua existindo; staff pode desativá-lo no admin
  (`ativo=False`) — é exatamente a autonomia desta arquitetura.

## 6. Deploy & segurança

- Migrações: 0054 (campos), 0055 (wipe demo), 0056 (backfill+basais).
- `TbCosmetico`/`TbConquista` já são CONTENT (dump_conteudo→loaddata);
  `definicao_json` viaja junto. Uploads (`css_file`, `asset_file`) ficam em
  MEDIA (servido em prod desde F1) — **não** viajam no content-sync; staff
  cadastra direto em prod (ou copia media/ manualmente).
- Sanitização hex/enum em TODA emissão de style inline (usuário comum nunca
  fornece definição — só escolhe temas do catálogo, validado por posse).
- `prefers-reduced-motion` cobre qualquer animação nova.

## 7. Pacotes de trabalho (execução por subagentes; Fable só audita)

- **WP1 (sonnet)** perfil-fx v3: remove sweep; partículas por `data-fx-*`
  (fallback classes legadas); reduced-motion atualizado.
- **WP2 (opus)** backend: campos+migração 0054, sanitizador, contexto,
  catálogo, templates (attrs, `<link>` css_file, bump `?v=3`), admin uploads,
  badges/conquistas `*_efetivo`, cards de /jogadores com vars.
- **WP3 (sonnet)** seletor-prévia (perfil + ficha), CSS das swatches em
  perfil.css.
- **WP4 (sonnet)** migrações 0055 (wipe) e 0056 (backfill+6 basais).
- **WP5 (opus)** verificação integrada (migrate, test Client em todas as
  páginas, greps de regressão, distribuir temas basais nos perfis demo).

Ordem: (WP1 ∥ WP2) → (WP3 ∥ WP4) → WP5 → auditoria Fable → commit/push.
