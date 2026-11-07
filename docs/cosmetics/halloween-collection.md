# Vigilia das Lanternas

## Versao Aprovada

O pacote final ja foi publicado no Git em `021de66`. `d2abb9c` corrigiu as
quinas ilustradas e colocou o fogo auxiliar atras do Jack. A limpeza de autoria
de novembro nao muda arte, manifesto, motor compartilhado ou dados do evento.

Tema, moldura e efeito sao independentes. O tema usa bordas raster ilustradas;
a moldura tem abertura transparente calibrada; o efeito sobrepoe o banner do
jogador sem substitui-lo. Todas as superficies usam o leitor compartilhado de
pacotes, nao um motor Python ou JS exclusivo para o item.

O efeito tem oito camadas-raiz:

1. Nuvens escuras transparentes.
2. Decoracao inferior esquerda.
3. Lanternas direitas estaticas.
4. Grupo de uma vela fina com prato raso.
5. Grupo de duas velas finas unidas pela cera no mesmo prato.
6. Grupo de tres velas finas unidas pela cera no mesmo prato.
7. Fogo auxiliar com dissolucao texturizada, atras do rosto.
8. Jack composto por duas pranchas do olhar a 30 fps, sorriso, aparicoes dos
   olhos e do sorriso, e iluminacao auxiliar mascarada.

As seis chamas das velas compartilham doze poses, com fases e movimentos
independentes. O Jack mantem ciclo de dezesseis segundos, pausas nos extremos,
contorno fixo e os fades artisticamente aprovados. Tempos e curvas exatos estao
nos manifestos, nao nas anotacoes de prototipos antigos.

## Fonte De Verdade

| Arquivo | Responsabilidade |
| --- | --- |
| `home/static/cosmetics/efeito-vigilia-das-lanternas.json` | Camadas, ordem, trajetorias, partes, mascaras e tempos finais |
| `home/static/cosmetics/moldura-vigilia-das-lanternas.json` | Moldura e calibracao do retrato |
| `home/static/cosmetics/tema-vigilia-das-lanternas.json` | Identidade do tema |
| `home/static/css/components/illustrated-theme-skins.css` | Bordas e cores por dados/skin |
| `home/cosmetic_packages.py` | Validacao generica dos pacotes e assets |
| `home/static/cosmetics/renderer.js` | Leitura compartilhada de partes e sequencias |
| `docs/cosmetics/build-halloween-preview.cjs` | Exporta os manifestos atuais para a previa offline |
| `docs/cosmetics/halloween-preview-data.js` | Copia gerada, nunca fonte primaria da animacao |
| `docs/cosmetics/20261029-halloween.html` | Previa da entrega aprovada, sem carregar estudos rejeitados |
| `docs/cosmetics/20261029-halloween.js` | Controles locais de tema/moldura/efeito/movimento/chama/fogo |

Assets principais: `vigilia-wax-{one,two,three}-v6.webp`,
`vigilia-flame-twelve-v3.webp`, `vigilia-jack-local30-{1,2}-v30.webp`,
`vigilia-jack-reference-smile-v27.webp`,
`vigilia-jack-cinematic-{eyes,smile}-fx-v28.webp`,
`vigilia-jack-light-v29.webp`, `vigilia-jack-light-mask-v29.png` e
`vigilia-jack-fire-textured-v32.webp`.

## Manutencao Segura

```powershell
node docs/cosmetics/build-halloween-rigs.cjs
node docs/cosmetics/build-halloween-preview.cjs
```

O primeiro comando agora somente confere o rig aprovado e seus arquivos. O
gerador antigo reconstruia o manifesto a partir de uma versao rejeitada; esse
comportamento foi desativado para impedir regressao acidental. Opcionalmente,
`--export-preview` tambem executa o segundo comando. Nenhum deles acessa banco.

A previa padrao sempre mostra os manifestos aprovados. Estudos antigos locais
continuam separados, mas nao sao dependencias nem recebem promocao automatica.
Nao interpretar instrucoes historicas de v8/v17/v19/v23 como tarefas atuais.

## Acesso E Publicacao

O resgate gratuito autorizado foi exclusivamente em **31/10/2026**, com termino
exclusivo em **01/11/2026 00:00 America/Sao_Paulo**. Esta manutencao nao reabre
o evento, nao altera preco ou permissao, nao cria concessoes e nao revoga posses.
Elegibilidade continua no catalogo/banco; preservar PKs, inventarios e selecoes.

Este lote documental nao exige migration ou nova atualizacao de dados. Para
mudancas futuras de arte, atualizar manifestos/assets versionados, exportar a
previa e conferir transparencias, tamanhos, reducao de movimento e ausencia de
arquivos faltantes antes do deploy pelo fluxo habitual `/site-update`.
