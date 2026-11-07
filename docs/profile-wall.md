# Perfis: personagens e mural

## Entrega

- O perfil publico usa a mesma identidade de card de `personagem_card.html`: retrato,
  moldura equipada ou de rank, nome, raca, classe, nivel e insignia. A projecao
  publica nao inclui formularios nem comandos de manutencao da ficha.
- O mural pertence ao perfil, inclusive ao alternar para o portfolio de mestre.
  Mostra dez comentarios por pagina, mais recentes primeiro.
- Contas ativas autenticadas podem publicar Markdown de ate 4.000 caracteres,
  inclusive no proprio perfil. Cada envio tem UUID para absorver repeticoes.
  Limite inicial: cinco envios em dez minutos por autor, incluindo removidos.
- Curtidas sao estado desejado (`true`/`false`), nao toggle por tentativa. Nao e
  permitido curtir o proprio comentario. O contador vem do servidor.
- Autor, dono do perfil e staff podem remover comentarios do mural. A remocao
  preserva texto, autoria, data e curtidas para auditoria; nao e exclusao fisica.
- O administrador pode consultar e remover comentarios no Django Admin.

## Arquivos E Contratos

| Arquivo | Responsabilidade |
| --- | --- |
| `home/models.py` | `TbPerfilComentario` e `TbPerfilComentarioCurtida`, limites e unicidade |
| `home/migrations/0166_profile_comments.py` | Duas novas tabelas e indices; sem migracao de conteudo ou alteracao de PKs existentes |
| `home/profile_comments.py` | Formularios, leitura paginada, visual dos autores, autorizacao, antispam, publicar/curtir/remover |
| `home/profile_comments_admin.py` | Moderacao administrativa, sem edicao de autoria ou exclusao fisica |
| `home/admin.py` | Registro do modulo administrativo |
| `home/views.py` | `public_profile_view` recebe `**wall_context(..., request=request)` |
| `home/urls.py` | Tres rotas POST do mural |
| `home/templates/home/partials/_personagem_card_identity.html` | Identidade compartilhada entre listagem privada e perfil publico |
| `home/templates/home/partials/personagem_card.html` | Mantem as acoes privadas existentes ao redor da identidade compartilhada |
| `home/templates/home/partials/_perfil_publico_hero.html` | Card completo de personagem e mural dentro do tema escolhido |
| `home/templates/home/partials/_profile_wall.html` | Compositor, comentarios, avatares, curtidas e paginacao |
| `home/templates/home/pages/perfil_publico.html` | Carrega CSS e JS do mural |
| `home/templates/home/base.html` | Carrega CSS pequeno do card, tambem usado nas outras previas |
| `home/static/css/components/character-card.css` | Projecao publica do card compartilhado |
| `home/static/css/pages/profile-wall.css` | Layout responsivo, contenção de imagens e texto, cores herdadas do perfil |
| `home/static/js/profile-wall.js` | Ferramentas de escrita, previa segura e curtida confirmada pelo servidor |
| `home/static/icons/lucide/` | Icones Lucide e licenca original |

Rotas:

- `POST /perfil/<username>/comentarios/`: `texto` e `chave_operacao` UUID; redireciona
  para o mural. Erros preservam rascunho limitado na sessao, sem publicar.
- `POST /perfil/comentarios/<id>/curtir/`: JSON `{"curtido":true}` ou formulario
  `curtido=true`. JSON retorna `{"ok":true,"curtido":true,"curtidas":1}`.
- `POST /perfil/comentarios/<id>/remover/`: exige permissao sobre o comentario;
  redireciona para o mural, sem excluir dados fisicamente.
- `GET /perfil/<username>/?comentarios_page=2#comentarios`: leitura paginada.

## Markdown, Imagens E Emojis

O texto e salvo bruto e escapado pelo template. A exibicao e a previa reutilizam
`renderBonfireMarkdownElement` e `sanitizeBonfireMarkdownHtml` de
`home/static/js/markdown.js`, sem criar outro motor de formatacao. O mural usa
`data-markdown-manual` para evitar renderizar duas vezes e perder links/imagens.
Widgets de selecao mecanica ficam desativados nesse contexto.

Imagens usam `![legenda](https://...)`; o compositor oferece insercao por URL.
Nao ha upload novo nem download de imagem pelo servidor. As imagens externas sao
carregadas pelo navegador, com `referrerpolicy=no-referrer`, e limitadas ao bloco
do comentario. Links recebem `nofollow ugc noopener noreferrer`. Scripts, handlers
HTML e protocolos perigosos nao sao executados.

Emojis Unicode funcionam no texto e no seletor inicial. Nao foram criados assets,
precos ou regras para um catalogo de emojis proprios. Quando existirem, sua
resolucao deve entrar no leitor Markdown compartilhado, nao em condicoes por
comentario ou perfil. Nao confundir curtida do comentario com reacoes por emoji:
essa primeira entrega tem somente a curtida solicitada.

## Verificacao E Ativacao

Testes locais, sem credenciais nem banco de producao:

```powershell
py -3.14 -m home.test_profile_comments --isolated
$env:PLAYWRIGHT_MODULE = 'CAMINHO_DO_NODE_MODULES/playwright'
node home/js_tests/profile_wall.e2e.cjs
```

O primeiro aplica somente a nova migration em SQLite em memoria e testa
persistencia, permissoes, repeticoes, limites e leitura. O segundo usa dados
ficticios renderizados pelos partials reais para testar desktop/mobile, imagens,
Markdown, emojis, bloqueio de scripts, curtidas e falha de conexao.

Previa visual local, sem gravacao de comentarios nem curtidas:

```powershell
node home/js_tests/profile_wall.e2e.cjs --serve 8898
```

Para disponibilizar no site real, o lote precisa ser commitado/pushado e receber
o `/site-update` habitual, incluindo `migrate` e `collectstatic`. Nao ativar apenas
os templates antes da migration. Nenhum dado ou schema de producao foi alterado
durante a implementacao local.

Ficam fora deste lote: notificacoes novas, emojis exclusivos, respostas encadeadas,
edicao de comentarios e mudancas em visibilidade de personagens. As regras de
privacidade existentes continuam sendo a fonte para selecionar os cards publicos.
