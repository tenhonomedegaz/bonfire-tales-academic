# Customizacao: catalogo leve e colecao da comunidade

## Entrega

O editor de perfil mostra tres seletores: tema, moldura e efeito. Cada um
mostra somente a escolha atual. O catalogo abre em dialogo, com miniaturas
estaticas, busca, categorias de tema e uma unica previa lateral. Nomes,
descricao e obtencao aparecem ao escolher um icone, nao abaixo de todos.

Experimentar nao equipa: Cancelar/Escape mantem a escolha; Aplicar atualiza
o campo do formulario. A gravacao continua sendo o botao Salvar Perfil e
os validadores de posse existentes. Itens bloqueados podem ser vistos, mas
nao aplicados, inclusive se alguem adulterar o botao no navegador.

O perfil publico e a ficha continuam usando o mesmo leitor de cosméticos.
O cabecalho do editor e neutro: nao baixa animacoes completas ao entrar.
O painel antigo e suas consultas de personagens/conquistas para previa foram
removidos do carregamento inicial. As secoes reais de conquistas, comunidade,
seguranca, assinatura e dados do usuario foram preservadas.

## Temas

- Classicos: predefinicoes de paleta, incluindo os gratuitos ja existentes.
  A preservacao desses acessos foi confirmada pelo usuario.
- Especiais: contornos/texturas ilustrados, como luas, ranks e o novo Colab.
  Novos temas especiais nao entram como gratuitos.
- Personalizado: mantem os controles de cores e os demais campos existentes.

`TbCosmetico.definicao_json.categoria` aceita `classico` ou `especial`.
O metadado e separado da sanitizacao de CSS e nao muda direitos de acesso.
Dados antigos sao classificados pela apresentacao publicada, sem regra por
nome de rank ou tema. Temas classicos nao recebem os antigos desenhos de
motivos vetoriais; os especiais ilustrados usam seus assets, nao esses motivos.

## Arte

Cinco molduras livres receberam PNG/WebP novos: Anel de Brasa, Pulso Arcano,
Friso Dourado, Coroa de Gelo e Tranca Verdejante. Materiais e ornamentos
sao reconheciveis, com menos detalhe que eventos/ranks e abertura calibrada
para o retrato. As versoes antigas foram preservadas.

Dois efeitos livres novos: Folhas da Trilha e Faiscas da Forja. Usam poucas
particulas pintadas nas laterais e movimento limitado do leitor existente.
Os efeitos livres antigos continuam disponiveis; suas miniaturas foram
capturadas do proprio render, sem inicializar todas as animacoes na pagina.

Conjunto Colab: moldura e tema Guardiao da Fogueira, mais o efeito Fogueira
Partilhada. Ferro escuro, cobre dourado, brasa e pequenos braseiros formam uma
identidade comum. O tema usa borda raster nine-slice; o centro do banner
continua pertencendo a imagem do usuario. O plano minimo preparado e Conde,
abrangendo os niveis superiores pelas regras de colaboracao existentes.
Nao foi inventado um direito permanente ou uma nova assinatura.

Fontes/direcao dos dez assets ImageGen integrados:
`community-art-sources.json`. Exportacao e thumbnails:
`build-community-assets.cjs`. Nenhum SVG substitui a arte das novas molduras,
bordas ou efeitos; somente miniaturas de paleta e icones de interface usam
formas simples. PNGs/WebPs finais ficam em `home/static/cosmetics/`.

## Arquivos Principais

- `home/cosmetic_picker.py`: metadados leves e consulta da previa escolhida.
- `home/cosmetics.py`: categoria validada, catalogo e permissoes existentes.
- `home/templatetags/cosmetic_packages.py`: lista somente metadados; nao le
  todos os pacotes para construir o seletor.
- `home/templates/home/includes/cosmetic_catalog.html`: seletor e dialogo.
- `home/static/js/cosmetic-catalog.js`: busca, cancelamento, foco, cache de
  ate 24 respostas, abort de requisicoes antigas e descarte das animacoes.
- `home/static/css/components/cosmetic-catalog.css`: layout estavel e responsivo.
- `home/templates/home/pages/perfil.html`: tres campos; sem painel de previa
  nem animacoes completas no cabecalho de edicao.
- `home/views.py`: contexto de categoria e retirada da previa antiga antecipada.
- `home/static/js/profile-effects.js`: motivos de tema separados das cores.
- `home/static/css/components/illustrated-theme-skins.css`: skin visual Colab.
- `home/static/cosmetics/catalog-presentation.json`: miniaturas publicas, sem
  precos, direitos ou inventario paralelo ao banco.

`GET /perfil/cosmeticos/previa/?tipo=moldura&key=verdant&escopo=perfil`
exige login, aceita somente itens ativos do catalogo e escopos validos,
nao grava nada e nao sincroniza/concede conquistas. Retorna arte publica,
estado de acesso atual e link de obtencao realmente publicado. A resposta
e privada e sem cache HTTP; o cache curto em memoria do navegador desaparece
ao recarregar. O servidor continua validando o POST de gravacao.

## Publicacao E Banco

**Nao foi alterado o banco da producao nem criada migration de conteudo.**
As cinco molduras existentes mudam de apresentacao pelos pacotes estaticos
apos deploy, mantendo slugs, PKs e acessos. O classico gratuito nao foi revogado.

Os cinco registros novos (dois efeitos livres e tres Colab) estao preparados
em `community-catalog-release.json`, com status `prepared-not-applied`.
Devem ser cadastrados no catalogo pelo admin ou pela manutencao de conteudo
existente, conferindo antes se cada slug ja existe. Nao usar restauracao de
backup por PK, nao incluir inventarios e nao sobrescrever um registro existente
com defaults. O modelo e TbCosmetico; nao sao novos casos no motor Python.

Sequencia de ativacao: revisar a previa, deploy do codigo/assets, cadastrar
somente os novos slugs ausentes e verificar a disponibilidade real por conta.
O acesso Colab usa `origem=colaborador` e `requer_plano=conde`; descricao
editorial nao concede acesso. Nenhum preco de loja foi inventado.

## Verificacao

Fixture isolada: `home/js_tests/community_picker_fixture.py --test`.
Cobertura de caminhos, escopos, posse, categorias, lista sem leitura antecipada
de pacotes, ausencia de grants, arquivos reais e transparencia. Nao usa o
PostgreSQL do projeto.

`home/js_tests/cosmetic_catalog_tiles.e2e.cjs` cobre controle e acessibilidade
com perfil/ficha; `home/js_tests/community_picker.e2e.cjs` usa as novas artes,
celular/desktop, Cancelar/Aplicar, bloqueados, descarte e carregamento sob demanda.

Previa interativa: `20261102-community-catalog.html`, servida pelo exemplo
local `serve-community-preview.cjs`. Ela usa dados demonstrativos publicos,
sem login, credenciais ou conexao ao banco. Nao e uma alteracao da producao.

Resultado: 63 testes Python passaram. Fluxos de perfil e ficha passaram em
390/1280 px, incluindo fallback sem JavaScript. A colecao nova passou com
artes reais em 390/1440 px: nenhuma consulta de previa na entrada, cache,
Cancelamento/Aplicar, itens bloqueados, limpeza e arquivos carregados.
Capturas locais: `../AmandaBot/scratch/community-picker-qa-20261102/` e
`../AmandaBot/scratch/community-picker-contract-20261102/`.
