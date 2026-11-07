# Efeitos de banner separados do tema

Estado final: reclassificacao aplicada em producao apos o `/site update`
confirmado pelo PO. Mesmas PKs54/55/56/61, 28 inventarios preservados, uma
selecao movida e nenhum conflito. Banner proprio e overlay conferidos juntos
no perfil real. Evidencia: `../qa/20261028-banner-effects-production.md`.
O roteiro abaixo fica como referencia; NAO repetir cadastro/concessoes.

## Decisao

Composicoes Lua Vermelha, Lua Negra, Lua de Cristal e Vigilia das Lanternas
passam de Tema para Efeito. Tema continua escolhendo a paleta; efeito adiciona
lua/nuvens/ornamentos sobre o banner enviado. Molduras permanecem molduras.
Nao reclassificar os demais temas de paleta por inferencia.

Os arquivos `efeito-*.json` reutilizam as mesmas artes, posicoes e animacoes dos
quatro `tema-*.json`. Os antigos manifestos sao mantidos durante a transicao,
para nao quebrar escolhas enquanto o banco ainda tem os registros como tema.
Nao ha regra Python especifica para uma lua nem nova migration de conteudo.

## Sobreposicao corrigida

`perfil.css` colocava a imagem propria no nivel1 e as camadas do pacote no0.
Agora imagem-base fica0, overlay1, ornamentos2 e identidade acima das camadas.
O banner publico tem contexto de empilhamento isolado. Regras das fichas foram
delimitadas para nao sobrescrever o contrato compartilhado, incluindo previa
dinamica. Cache CSS atualizado. Sem transformar o banner em imagem do efeito.

## Aplicacao do dado em producao

Estado nesta entrega: codigo/assets/testes locais. A producao ainda usa os
tipos antigos ate publicar o codigo e executar a acao abaixo.

1. Publicar pelo `/site update` habitual. Nao trocar tipos antes de os
   manifestos `efeito-*` e a correcao de CSS estarem instalados.
2. Fazer backup pelo mecanismo administrativo ja existente antes da alteracao.
3. Em `/admin/home/tbcosmetico/`, selecionar SOMENTE os registros existentes:

| PK atual | Origem | Destino |
| --- | --- | --- |
| 54 | tema-lua-vermelha | efeito-lua-vermelha |
| 55 | tema-lua-negra | efeito-lua-negra |
| 56 | tema-lua-cristal | efeito-lua-cristal |
| 61 | tema-vigilia-das-lanternas | efeito-vigilia-das-lanternas |

4. Acao **Reclassificar tema / efeito / moldura**, destino **efeito**.
   Marcar **Limpar css_class da categoria anterior** para nao carregar
   `theme-data` como classe de efeito. Conferir os quatro slugs e confirmar.
5. Reler catalogo/inventarios e testar banner proprio + paleta independente.

A acao e generica e exclusiva para superuser. Valida TODO o lote antes de
gravar, exige manifesto de destino valido, bloqueia colisao de slug e ofertas
ativas, usa transacao e registra ator/contagens no historico administrativo.
Preserva PKs, inventarios, suspensoes, direitos e registros financeiros.
Nao criar outros quatro registros, nao copiar grants nem repetir a carga56.
Repetir no tipo de destino e no-op.

Escolhas salvas de perfil/ficha sao movidas para Efeito quando o destino esta
vazio/default; o Tema volta ao padrao. Caso ja haja outro efeito escolhido,
ele e preservado e a acao reporta conflito para decisao individual. A posse do
efeito migrado permanece, mesmo quando nao e equipado automaticamente.
Nao substituir silenciosamente uma escolha por outra.

`catalog-draft.json` e `discovery-editorial.json` agora usam os slugs de efeito.
Sao configuracao desejada, nao prova de que o banco remoto foi reclassificado.
As oito concessoes para os sete admins permanecem restritas por inventario;
esta alteracao nao cria concessao automatica nem libera usuarios comuns.

## Arquivos e evidencias

- `home/cosmetic_reclassification.py`: operacao atomica generica.
- `home/admin.py` e template `admin/home/tbcosmetico/reclassificar.html`: acao.
- `cosmetic-presentation.css`, `perfil.css` e versoes dos links: empilhamento.
- `home/static/cosmetics/efeito-{lua-*,vigilia-das-lanternas}.json`: pacotes.
- `home/test_cosmetic_reclassification.py`: identidade, selecoes, conflitos,
  permissao, rollback, colisoes, ofertas e repeticao.
- `home/test_banner_effect_packages.py`: paridade de arte e paleta independente.
- `home/js_tests/cosmetic_layer_layout.e2e.cjs`: pilha real nas seis superficies,
  desktop/mobile, com banner proprio, renderizacao inicial/dinamica e ranks.

Validacao local concluida; conferencia remota depende da publicacao acima.
As artes originais e a animacao de rank nao foram redesenhadas.
