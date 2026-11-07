# Catalogos, temas de rank e apresentacao compartilhada

## Escopo

Esta entrega troca os seletores visiveis de moldura e efeito por catalogos com
amostras, busca, estado selecionado e requisitos de desbloqueio. Os selects
originais permanecem como contrato de envio e alternativa sem JavaScript.
Nao altera preco, saldo, assinatura, rank mecanico ou permissao de personagem.

## Dados e direitos

- `home/migrations/0165_rank_themes.py`: renomeia apenas os nomes visiveis de
  Elo para Rank; slugs, PKs, inventarios e referencias permanecem intactos.
- Adiciona sete temas de rank ao catalogo e as conquistas permanentes existentes.
  Cada marco agora libera moldura aberta, fechada e tema. O backfill inclui
  direitos historicos, sem desfazer suspensoes ou revogacoes da administracao.
- Os temas usam `definicao_json`, incluindo paleta e `motif`. O Python valida
  uma lista de motivos genericos; nao possui uma implementacao para cada rank.
- As colecoes Lua Vermelha, Lua Negra, Lua de Cristal e Halloween ja possuem
  pacotes artisticos em `home/static/cosmetics` e definicoes em
  `docs/cosmetics/catalog-draft.json`. Continuam sem ativacao comercial ou preco
  inventado. A exibicao no ambiente de demonstracao nao concede acesso real.

## Arquivos de apresentacao

| Arquivo | Responsabilidade |
| --- | --- |
| `home/templates/home/includes/cosmetic_catalog.html` | Tiles, rotulos, bloqueios e alternativa select |
| `home/templatetags/cosmetic_packages.py` | Amostra publica da arte, sem conceder posse |
| `home/static/js/cosmetic-catalog.js` | Busca, teclado, sincronizacao e eventos do select |
| `home/static/css/components/cosmetic-catalog.css` | Grade responsiva e estado selecionado |
| `home/cosmetic_packages.py` | Validacao dos manifestos e da abertura do retrato |
| `home/static/cosmetics/moldura-elo-*.json` | Centro e diametro da abertura de cada arte |
| `home/static/cosmetics/renderer.js` | Mesmo encaixe da foto em todas as superficies |
| `home/static/css/components/cosmetic-presentation.css` | Foto calibrada e transicao da viseira |
| `home/static/js/profile-effects.js` | Camada decorativa independente do tema |
| `home/static/css/components/profile-effects.css` | Efeitos distintos e brilho periodico das molduras simples |
| `home/static/css/components/profile-theme-motifs.css` | Motivos dos temas e cores do editor privado |
| `home/static/js/tema_swatch.js` | Aplicacao imediata da paleta e do motivo escolhidos |

`aperture` usa porcentagens da celula aberta da imagem: `cx`, `cy`, `diameter`.
O par aberto/fechado compartilha os mesmos valores, sem deslocar a foto durante
a animacao. A abertura foi medida no alpha da arte, nao pela posicao da caixa
externa. Alterar a arte requer recalibrar esses dados, nao criar uma regra Python.

Tema, moldura e efeito sao escolhas independentes. Efeito `none` nao deve
herdar particulas de outro efeito. Camadas decorativas nao recebem cliques e
respeitam movimento reduzido; nenhum ajuste salva o perfil antes do envio.

## Publicacao

Usar o fluxo normal `/site update`, incluindo migrations e estaticos. Nao e
necessario restaurar backup ou executar um comando extra para liberar os temas.
Esta etapa foi validada com dados sinteticos locais; nao escreve na producao.

Para futuras colecoes, cadastrar a paleta e o motivo no banco, preparar o pacote
artistico se necessario e definir a regra de acesso. Nao duplicar templates por
rank nem adicionar condicionais por nome de cosmetico.
