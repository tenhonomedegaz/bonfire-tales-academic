# Bonfire Tales RPG - Copia Academica e Portfolio

Copia academica publica do codigo do Bonfire Tales RPG, uma plataforma web para
centralizar regras, personagens, missoes e operacoes de uma comunidade de RPG.
Preparada para referencia no Trabalho de Graduacao em Analise e Desenvolvimento
de Sistemas e para apresentacao de portfolio de Helio Augusto Goncalves Vieira.

**Estado: em desenvolvimento, com pendencias conhecidas. Nao e uma demonstracao
de produto concluido nem uma copia do banco de producao.**

## Comece por aqui

- [Contexto para orientacao e manutencao manual](docs/academic/CONTEXTO_PARA_ORIENTACAO.md)
- [Pendencias consolidadas, arquivos e criterios de aceite](PENDENCIAS.md)
- [Proveniencia e exclusoes do snapshot](docs/academic/SNAPSHOT.json)
- [Arquitetura evolutiva original](ARQUITETURA_EVOLUCAO_BONFIRE.md)
- [Regras declarativas e vocabulario](docs/criador-personagem/vocabulario-tags-json.md)

## Escopo tecnico

Python e Django no servidor; PostgreSQL na persistencia; templates Django,
JavaScript e CSS no cliente. Integra OAuth do Discord, planilhas de fichas,
catalogos de regras, economia e uma API administrativa auditada. O laboratorio
VTT 2D e uma frente experimental, nao o VTT 3D completo.

As mecanicas combinam dados/tagueamento e leitores genericos. O codigo ainda
tem adaptadores e divida tecnica, especialmente na transicao do Cacador;
o objetivo arquitetural nao deve ser confundido com implementacao integral.

## Origem desta copia

- Branch de origem: `dev`.
- Commit de referencia: `b9920a3343f7909cc74815e2a4a8fb0d6718f32e`.
- Data desta atualizacao: 09/11/2026.
- Historico Git independente: commits antigos do repositorio privado nao foram publicados.
- A documentacao inclui relatos de QA posteriores a esse commit, explicitados no manifesto.
- Esta copia nao acompanha a `dev` automaticamente e nao publica alteracoes em producao.

## Marco de Gestao e Revisao de Historias

Este marco incorpora a central de gestao por tarefas, cargos e permissoes,
regularizacao de treinamento, correcao auditada de dados da ficha e integracao
das filas editoriais, dos mestres e dos anuncios. Historias de personagens agora
possuem rascunho, envio, parecer do Loremaster, devolutiva e reenvio com versoes.
Inclui as correcoes recentes de Cacador/charbuilder e configuracao de ficha importada.

Consulte [arquitetura deste marco](docs/academic/CENTRAL_GESTAO.md) e
[pendencias atualizadas](docs/academic/PENDENCIAS_ATUALIZADAS.md).
As migrations 0178 a 0184 representam estruturas/contratos genericos, nao uma
copia de conteudo real. Publicar codigo nao significa implantar ou aprovar dados
na producao. Os 71 testes focados do lote operacional passaram; isso nao e uma
certificacao da suite completa nem da reproducao sem os catalogos excluidos.

## Execucao local

Requer Python **3.12 ou superior** (Django 6) e PostgreSQL para o ambiente completo.
Use uma base e contas exclusivamente locais. Nunca reutilize o ambiente de producao.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Defina uma chave local e os dados de um PostgreSQL local no .env.
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

**Limites da reproducao:** o catalogo de regras nao e preenchido automaticamente
nesta copia. Fixtures, pacotes de publicacao, dumps, historicos operacionais e
dados reais foram excluidos. As tabelas compartilhadas com o bot sao modelos
`managed=False`: `migrate` nao cria essas tabelas. Funcoes dependentes do bot,
Google, pagamento e catalogos exigem configuracao e dados sinteticos proprios.
Uma base vazia nao reproduz o conteudo nem o comportamento integral da producao.

Varios testes oferecem modo `--isolated`, com SQLite descartavel. Consulte o
cabecalho do teste antes de executar; nao aponte testes para bancos reais.
Exemplo sem contas externas: `python -m home.test_character_log_review --isolated`.
Testes de pacotes/fixtures excluidos nao passam sem uma fonte sintetica equivalente;
isso e uma limitacao da distribuicao publica, nao motivo para copiar dados reais.

## Contexto academico e autoria

O TG fornecido durante esta preparacao descreve desenvolvimento incremental,
modelagem relacional, integracoes, regras por tags e limitacoes de validacao.
Seu texto esta defasado em relacao ao snapshot; o PDF nao foi republicado aqui.
O repositorio documenta a implementacao, nao substitui o artigo nem comprova
sozinho resultados de usabilidade, seguranca ou ganhos quantitativos.

O projeto teve colaboracao da comunidade, orientacao do Product Owner, QA de
outros participantes e desenvolvimento assistido por IA. Nao atribuir ao autor
individualmente todo o frontend, toda arte ou todos os componentes de terceiros.

## Direitos e seguranca

Publico nao significa automaticamente licenciado para redistribuicao comercial.
Nao foi atribuida uma nova licenca ao projeto sem decisao dos titulares.
Licencas de bibliotecas e componentes incluidos foram preservadas; textos de
RPG, marcas e artes podem possuir direitos especificos. Nao usar este snapshot
como autorizacao para redistribuir catalogos ou ativos de terceiros.

Nao envie senhas, arquivos `.env`, backups ou dados de jogadores em issues.
Relatos de seguranca devem ser enviados de forma privada ao mantenedor.
