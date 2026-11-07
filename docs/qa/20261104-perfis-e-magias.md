# Pendencias Recebidas Em 04/11/2026

Estado: **registradas, nao corrigidas nesta rodada**. Pedido atual: concluir a
caminhada L4 em execucao; depois priorizar magias de subclasse junto ao VTT.
Este arquivo complementa `20261026-relatos.md` e `20261102-relato-conteudo.md`,
sem sobrescrever seus estados ou reabrir itens entregues.

## QA-PERFIL-20261104-01: Inserir Imagem No Celular

Relato da Kat: depoimentos foram publicados e testados; no celular o campo para
colar a imagem fica parcialmente escondido ("comido"), levando ao abandono da
insercao. A captura nao mostra o momento exato do recorte: causa ainda nao
reproduzida. Nao concluir que publicar, curtir ou persistir comentarios falhou.

Arquivos a revisar:

- `home/static/js/profile-wall.js`: abertura do campo URL, foco e selecao do texto.
- `home/templates/home/partials/_profile_wall.html`: compositor e ferramenta URL.
- `home/static/css/pages/profile-wall.css`: largura, overflow e controles mobile.
- `home/templates/home/pages/perfil_publico.html`: integracao e containers externos.
- `home/js_tests/profile_wall.e2e.cjs`: reproducao integrada com viewport estreito.

Aceite: em 360/390 px, com teclado virtual quando disponivel, campo inteiro e
acoes de inserir/cancelar acessiveis, sem corte/overflow; inserir URL e manter
texto/posicao do cursor. Conferir foco, previa e retorno ao editor. Nao adicionar
upload nesta correcao: clipboard/armazenamento externo e a frente separada
QA-MIDIA-20261103-01. Botoes sem resposta continuam sob QA-PERFIL-20261103-01.

Fonte: `codex-clipboard-99e1650b-e567-48f4-956f-535d50c0808a.png`.

## QA-JOGADORES-20261104-01: Paginacao Permanece No Rodape

Ao avancar a lista de jogadores, a pagina conserva o scroll inferior em vez de
mostrar o inicio dos novos resultados. Codigo atual em
`home/templates/home/pages/jogadores.html`, funcao `updatePlayers`: substitui
`.players-page`, atualiza history e foca `.players-meta` com `preventScroll:true`,
sem reposicionar a tela. E um indicio concreto, nao uma reproducao em producao.

Alteracao prevista: depois da resposta vigente e da troca dos resultados,
posicionar no inicio util da listagem (considerar cabecalho fixo). Preservar
consulta, ordenacao, navegacao por teclado, abrir em outra aba e fallback sem JS.
Tratar voltar/avancar do navegador separadamente, sem apagar restauracao de
scroll por automatismo. Respeitar reducao de movimento; nao animar por obrigacao.

Revisar tambem `home/test_jogadores_public_privacy.py` para preservar privacidade
e os testes de navegador da listagem existentes antes de criar outra fixture.
Aceite: proxima/anterior exibem inicio dos novos resultados em desktop/mobile,
com filtros intactos; resposta atrasada nao muda foco/scroll da resposta recente.

Fonte: `codex-clipboard-03426d11-5497-4b6c-a90a-c7f6cf24befe.png`.

## MEC-MAGIAS-20261104-01: Prioridade Compartilhada Ficha/VTT

Concessoes e listas de magias de subclasse devem vir de dados e tags. Nao
implementar if/dispatch por nome de subclasse. Nao presumir que a ausencia foi
provada: auditar dados existentes, regras versionadas e concessoes materializadas.

Plano de execucao, arquivos e aceite: [Magias de subclasse](../vtt/subclass-spells-plan.md).
Referencia integral fornecida pelo PO preservada em
`../vtt/references/subclass-spells-user-20261104.txt`. Nenhuma lista foi aplicada
no banco nesta rodada; nao confundir arquivo de referencia com conteudo publicado.
