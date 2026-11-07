# Escolhas de marcos de aventuras

Epic Boon pertence ao marco de **160 aventuras**, depois dos 20 niveis de classe.
Lenda e o marco de 200 aventuras; nao repete a escolha anterior e nao concede
niveis extras de classe. ASIs comuns continuam sem talentos epicos.

## Dados e tags

O motor generico `home/progression_choices.py` le opcoes de jogo do tipo
`Marco de Progressao`. A migration 0162 insere, somente se ausente, UMA politica:

- slug: `progressao-epic-boon`
- nome: `Epic Boon`
- tags: `progression{adventures:160,level:20}` e `pick:talento:1(tipo:epico)`

Essa migration nao cria talentos, nao altera efeitos individuais e nao muda a
estrutura do banco. Os limiares e a categoria sao dados editaveis na opcao de
jogo, pelo admin ou pela API de catalogo. O slug deve permanecer estavel depois
de concedido: identifica a escolha persistida. Cada politica representa uma
concessao de um talento. Aumentos, dados, efeitos e limites vem das tags do talento.

## Fluxo e arquivos

1. `home/views.py`: pendencias do level-up incluem marcos elegiveis; a ficha
   mostra o botao de concluir escolhas mesmo se o nivel de classe ja e 20.
2. `home/templates/home/pages/subir_nivel.html` e `home/static/js/subir_nivel.js`:
   etapa de marco, talento, atributo e escolhas adicionais, com previa sem gravacao.
3. Acao do lote: `{"tipo":"marco","payload":{"marco":"progressao-epic-boon",
   "talento":"ID","talento_attr":"DES","talento_picks":{}}}`.
4. O servidor trava o personagem na transacao, revalida limiar, categoria,
   propriedade previa, atributo e escolhas. O resolvedor generico de picks
   registra a origem estavel e o talento; o detalhe guarda o atributo escolhido.
5. `home/character_engine.py` deriva o efeito das tags, sem criar bonus fixo
   de +1 ou +2. Reabrir, reenviar ou atingir Lenda nao gera outro talento.

Concessoes globais de marco usam o catalogo corrente, independentemente do
snapshot de uma classe. `home/versioned_origins.py` preserva os demais talentos
selados e reconhece apenas essas concessoes explicitas como fontes globais.

## Ativacao

Atualizar o site pelo fluxo habitual `/site-update`, incluindo migrations e
estaticos. Nao e necessario restaurar backup, criar personagem novamente ou
rodar um script de importacao de talentos. Os 31 talentos ja publicados devem
continuar no catalogo. Personagens existentes com 20 niveis e 160+ aventuras
ganham uma pendencia de marco ao abrir a ficha; nao sao recriados. Concessoes
manuais legadas da mesma categoria, registradas no nivel do marco ou depois,
tambem contam como cumpridas para evitar uma segunda concessao.

Teste focado: `home.test_progression_choices`. Cobre limiar, catalogo, previa,
persistencia, efeito, teto, replay, rollback, escolhas adicionais e pagina.
