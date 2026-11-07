# Solo Sepulcral / Grave Ground

Referencia entregue pelo PO em 04/11/2026: captura
`codex-clipboard-0e4b94b2-2737-4fb0-bf66-30da880aa5e7.png`, AU p.40.
Fonte de dados traduzida: `home/content_packages/grave_ground_20261104.json`.
Nenhum comportamento foi criado em Python por nome da magia.

Cadastro confirmado na producao pela API em 04/11/2026: `magia` PK **583**,
slug `solo-sepulcral`. Consulta previa por slug retornou zero; CREATE usou chave
de idempotencia persistida e GET posterior conferiu todos os campos do pacote.
Nao houve sobrescrita, deploy ou alteracao em personagem/subclasse. A concessao
de Exorcistas depende do lote de tags, ainda nao aplicado.

## Regras Preservadas

- Necromancia, 5o circulo, Acao, alcance 120 ft (36 m no padrao Bonfire).
- V, S, M: um punhado de terra de sepultura, sem custo/consumo acrescentado.
- Concentracao por ate um minuto.
- Ate quatro quadrados de 10 ft de lado, dispostos pelo conjurador; cada um
  contiguo a pelo menos outro. Nao substituir por um circulo/cubo unico nem
  impor que todos os quadrados formem um unico componente conectado.
- Terreno dificil somente para inimigos.
- Salvaguarda de FOR na aparicao, ao entrar ou ao terminar turno na area,
  limitada a uma por criatura por turno (nao uma por conjurador/global).
- Falha: 6d6 necrotico e -1d6 em TODAS as rolagens de dano da vitima ate o fim
  do proximo turno dela. Nao substituir por desvantagem, metade ou reducao de
  dano recebido. Sucesso nao recebe dano/penalidade; a fonte nao declara metade.
- +1d6 por circulo do espaco acima do quinto, nao por nivel do personagem.

Listas-base: Clerigo, Warlock (Mistico no projeto) e Mago. A concessao pela
subclasse Exorcistas do Cacador vem da habilidade taggeada; NAO adicionar Cacador
a lista global, o que liberaria a magia para todas as suas subclasses.

## Cobertura Das Tags E Limite Atual

O pacote usa somente DSL existente, sem erros/avisos do validador:
`instant{save{str}, on_fail{dmg:6d6(necrotico)}}` e
`upcast{per:slot_level_above_base, dmg:+1d6}`. Sao o pacote pontual de
teste/dano e a escala, nao um executor integral da area persistente.

Ficam para suporte GENERICO no VTT: selecao dos quadrados e contiguidade, terreno
com filtro de inimigo, eventos de aparicao/entrada/fim de turno, limite por
vitima/turno, debuff de rolagem com expiracao por alvo e concentracao. Preservar
essas regras na descricao ate haver contrato/executor apropriado. Nao cadastrar
metade no sucesso, aura presa ao personagem ou debuff global como aproximacao.
As tags da magia nao sao incorporadas as passivas globais do ator no laboratorio.

Branding Smite -> Shining Smite foi confirmado explicitamente pelo PO na mesma
data e registrado no arquivo de equivalencias, sem renomear ou duplicar o
registro existente de Golpe Brilhante.
