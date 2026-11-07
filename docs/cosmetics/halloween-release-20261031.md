# Vigilia das Lanternas: release aprovada

O PO aprovou a composicao v32 em 31/10/2026 e autorizou resgate gratuito
somente nesse dia. Este documento substitui os estados de candidata das
anotacoes de estudo anteriores para esta entrega.

## Conteudo Publicado

`home/static/cosmetics/efeito-vigilia-das-lanternas.json` recebe o conteudo
integral aprovado de `halloween-fire-textured.json`. O leitor continua
generico: atlas, partes, mascara local e trilha de escurecimento separada.
Nao ha comportamento por nome de item nem regra nova de banco.

O pacote usa oito camadas: cenario transparente, lanternas, tres grupos de
velas finas, o rig do rosto e fogo auxiliar. O rosto tem seis partes e
olhar a 30fps. As chamas usam o mesmo fade texturizado do rosto, mantendo
cor/registro/tempos, com fim dos olhos junto ao escuro e sorriso por ultimo.
Todos os assets usados ficam em `home/static/cosmetics/` e cada um tem no
maximo 4MiB; o manifesto compactado ocupa menos de 64KiB.

```text
node docs/cosmetics/promote-approved-package.cjs docs/cosmetics/halloween-fire-textured.json
node docs/cosmetics/build-halloween-preview.cjs
```

O primeiro comando promove dados aprovados e verifica referencias locais;
o segundo atualiza a previa a partir do mesmo manifesto. Estudos antigos
e arquivos temporarios nao devem sobrescrever a release por engano.

## Resgate Gratuito

A configuracao desejada esta em `halloween-2026-free-claim.json`. Usar os
modelos e os formularios administrativos existentes, nao uma migration.

| Campo | Valor |
| --- | --- |
| Evento | `vigilia-das-lanternas-2026-10-31` |
| Itens | Tema, moldura e efeito da Vigilia; nenhuma das tres luas. |
| Origem do catalogo | `evento_manual`, ativo, preco zero. |
| Oferta | Ativa, custo de braseiros zero. |
| Inicio inclusivo | 31/10/2026 00:00 America/Sao_Paulo = 31/10 03:00 UTC. |
| Fim exclusivo | 01/11/2026 00:00 America/Sao_Paulo = 01/11 03:00 UTC. |
| Publico | Qualquer conta autenticada, mesmo sem personagem. |
| Depois do resgate | Posse permanente; encerrar a oferta nao retira o item. |

Resolver PKs por slug no destino. Preservar inventarios/concessoes anteriores,
criar somente a linha de tema se estiver ausente, e nao marcar `origem=livre`
(isso daria acesso sem resgate e fora do prazo). O servico existente usa
`now >= ends_at` para negar novos pedidos, inclusive formularios antigos,
e mantem idempotencia/posse de quem ja resgatou.

Pagina do jogador: `/cosmeticos/eventos/` (nome de rota
`event_cosmetic_shop`). A disponibilidade tambem
aparece no catalogo de cosmeticos e aponta para a oferta vigente.

## Implantacao

Enviar a `dev` e instalar pelo `/site-update` do BonfireBot. A atualizacao
de arquivos nao substitui a configuracao das ofertas em producao; conferir
as duas etapas separadamente. Cache de CSS/renderizador deve ser renovado.
Nao precisa de shell remoto, novas credenciais, migration ou exclusao de
personagens. As ofertas encerram pela data; nenhum job precisa acordar
para desativa-las.
