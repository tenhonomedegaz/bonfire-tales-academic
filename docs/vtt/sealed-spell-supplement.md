# Complemento Aditivo De Catalogo Pinado

## Diagnostico

A API corrigida selecionou a revisao ativa do Cacador:
`da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289`, modo
`configured`. A publicacao ainda usa `HUNTER_CREATOR_RULESET_CHECKSUM`, sem
ponteiro `TbClassPublication`. O catalogo possui 80 concessoes de tabela para
oito Ordens, mais tres beneficios extras, pelo leitor legado existente.

Solo Sepulcral / Grave Ground existe na producao como magia 583, mas nao no
catalogo imutavel dessa revisao. O leitor `home.hunter_spells.grants_at` recusa a
Ordem dos Exorcistas a partir do nivel 17. Nao e ausencia das oito tabelas nem
falha de deploy da consulta. A fonte viva e o pinado sao catalogos distintos.

Os payloads de referencia vieram somente das entradas imutaveis do backup de
28/10 cujo checksum de ruleset coincide com a API ativa. Todos os hashes de
revisao e vinculos foram verificados; nenhuma linha de jogador foi restaurada,
exportada para o plano ou usada como autoridade sobre dados atuais. A magia
nova veio do GET atual da API, com ETag conferido.

## Plano Restrito

`home/content_packages/subclass_spell_sealed_plan_20261104.json` e uma proposta,
nao recibo de aplicacao. Contem dois payloads para operacoes existentes/nova:

1. `spell-catalog-revision-preview` e `spell-catalog-revision`: acrescentar somente
   a magia revisada, copiando os campos do registro atual com versao coincidente.
   Nao atualizar as demais magias com o catalogo vivo; preservar manifesto e
   dependencias, rejeitando qualquer colisao de PK/slug.
2. `class-revision-preview` e `class-revision`: acrescentar as tags das concessoes
   nas oito habilidades existentes do snapshot. Preservar todas as demais
   propriedades, Ordens legadas, recursos e marcadores da revisao.

O suplemento e generico, sem nomes de classes/magias no controlador. As regras
continuam nos dados; nao existe migration por magia ou executor especifico.
Limites, escopos e idempotencia estao em `docs/catalog_api.md`.

Alvos calculados no ensaio isolado, a confirmar pelas previas da producao:

- Suplemento de magia: `d9a4498ed4bf6f21212fbab5d598dec406e11255bdc1b9507216505641b36f53`.
- Com tags das oito fontes: `95b5bdfb2f5bdec9d50cb42e0689bbd5e9643287a1b52ba6bd1be64c4376520d`.

Se fonte, base ou previa divergirem, parar e refazer a comparacao. Nao impor
checksum, PK ou ETag de um arquivo antigo. Nao configurar um alvo antes de sua
criacao e conferencia pela API. Guardar intencoes/recibos e repetir o mesmo UUID
e corpo em caso de interrupcao.

## Ativacao Separada

Primeiro instalar as operacoes pelo `/site-update`, depois criar/conferir as
duas revisoes pela API. Nenhuma delas altera configuracao ou personagem.
Para este ambiente legado, a ativacao exige trocar o checksum configurado para
o alvo confirmado e reiniciar pelo fluxo monitorado. O valor anterior fica
registrado para rollback; nao excluir nenhuma revisao antiga.

Nao usar `class-publication` cegamente: o contrato comum exige apresentacao de
catalogo, enquanto o alvo preserva a apresentacao legada. Forcar esse campo
sem consolidar a pagina poderia reintroduzir duplicatas e textos sem formatacao.
Fichas ja pinadas nao sao migradas automaticamente; isso continua uma etapa
separada, com comparacao e preservacao das escolhas de cada personagem.

## Evidencia E Limites

- Doze testes focados da operacao: previa readonly, versao concorrente, colisao,
  preservacao da base, repeticao, escopos e nao ativacao.
- Ensaio em SQLite exclusivamente em memoria, com o codigo real de criacao de
  revisoes e resolucao de concessoes. Base recomposta com o mesmo hash ativo;
  uma magia adicionada, oito fontes taggeadas, 160 combinacoes Ordem/nivel sem
  erros ou concessao antecipada. O catalogo original continua reproduzindo a
  falta da magia nos niveis 17-20, comprovando a diferenca do complemento.
- Isso nao prova criacao real de personagem, migracao de perfis antigos,
  concorrencia PostgreSQL, conjuracao integral, area ou concentracao no VTT.

Evidencia local sem segredos:
`AmandaBot/scratch/subclass-spells-20261104/hunter-sealed-proposed-audit.json`.
