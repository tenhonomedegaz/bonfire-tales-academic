# Auditoria das classes reworkadas e importacao do Bardo

Data: 2026-07-24

## Resultado

A pasta `ref/Classes Reworkadas` contem fontes para oito classes:

| Classe | Estado anterior no banco | Estado apos esta rodada |
|---|---|---|
| Barbaro | Reworkada | Sem alteracao |
| Bardo | Versao anterior | Reworkada |
| Clerigo | Reworkada | Sem alteracao |
| Feiticeiro | Reworkada | Sem alteracao |
| Guerreiro | Reworkada | Sem alteracao |
| Ladino | Reworkada | Sem alteracao |
| Monge | Reworkada | Sem alteracao |
| Paladino | Reworkada | Sem alteracao |

As divergencias aparentes das outras sete classes eram rotulos genericos da
tabela de progressao, como `Caracteristica de Colegio`, `Magias de Dominio` e
nomes alternativos do ASI. As habilidades nomeadas e seus niveis ja
correspondiam as fontes reworkadas.

Artifice, Cacador, Druida, Mago e Mistico nao possuem arquivo em
`ref/Classes Reworkadas`. Portanto, nao ha uma fonte nova nessa pasta contra a
qual seja possivel confirmar outro rework.

## Bardo

- 78 habilidades de classe/subclasse importadas do HTML.
- 14 recursos de progressao compactados em `valores_json`.
- 14 Acordes de Poder cadastrados como `TbOpcaojogo`.
- 8 Bailados de Combate cadastrados como `TbOpcaojogo`.
- Acessos por nivel cadastrados em `TbAcessoopcao`.
- Metadados de classe, equipamento e multiclasse atualizados.
- O builder oferece 2 truques e 6 magias no nivel 1.
- Acordes: 2 no nivel 2, chegando a 7 no nivel 18.
- Bailados: 2 no nivel 3, chegando a 5 no nivel 18.
- `Inspiração Superior` movida para o nivel 18.
- Todos os oito Colegios foram substituidos pela versao da fonte.
- A importacao apaga fisicamente todas as habilidades, recursos e acessos de
  opcao do Bardo antes de reconstruir o conjunto canonico.
- As 23 referencias `dono + slug` exclusivas da versao anterior foram
  auditadas: nenhuma sobrevive no banco nem e citada por outro conteudo.
- Opcoes antigas especificas do Bardo sao removidas quando ficam orfas.

O comando reproduzivel e:

```powershell
.\.venv\Scripts\python.exe manage.py import_bardo_rework
.\.venv\Scripts\python.exe manage.py import_bardo_rework --apply
```

Sem `--apply`, o comando apenas valida a fonte e relata a diferenca.

## Validacao

- `manage.py validate_tags`: `ERROR=0 WARN=0 INFO=0`.
- Testes dedicados: 7 testes, todos aprovados.
- O fluxo generico de `pick:opcao` le Acordes e Bailados sem ramificacoes
  hardcoded no character builder.
- Um teste de regressao rejeita explicitamente cada habilidade removida da
  versao anterior no seu antigo dono.

## Producao

Aplicar pelo admin console, na acao de merge de conteudo:

`ref/backups/restore_consolidado_bardo_rework_limpo_20260724_191215.json`

SHA-256:

`d0225ceb10df8a39ca6e238b4aa4b9488a1339ad6fde791edf5a0ecd2bc3845a`

O arquivo omite mundo/mapa e memoria de usuario. Essas tabelas sao preservadas
na producao pelo restaurador.
