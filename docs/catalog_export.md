# Exportador de catalogos para Excel

## Acesso

Rota: `/admin/catalog-export/`. O console `/admin/server-logs/` inclui o atalho
**Exportar dados (Excel)** para superusers ativos. Login de staff sem superuser
nao permite exportar. Nao usa a chave de API nem a senha de comandos do console.

1. Selecione as tabelas/catalogos.
2. Marque as colunas; a PK e sempre incluida para identificar os registros.
3. Adicione filtros por campo. Filtros sao combinados com E: igualdade por tipo
   e busca Contem para campos textuais. Nao aceita SQL nem caminhos ORM arbitrarios.
4. Quando houver campo de data, escolha esse campo e o periodo. O dia final e
   incluido por inteiro, usando o fuso do servidor. Nao se inventa uma data para
   catalogos que nao possuem campo temporal.
5. Confira a previa (quantidade e ate tres amostras por tabela) e baixe o Excel.

## Conteudo do arquivo

- Uma aba por catalogo e uma aba `_exportacao` com selecao, contagens, horario,
  tabela real e identificacao do administrador que gerou o arquivo.
- PKs e FKs permanecem IDs; nao sao convertidas em nomes nem reassociadas.
- Markdown e JSON completos sao preservados. A previa mostra somente um trecho.
- Decimais e inteiros com mais de 15 digitos sao texto para evitar arredondamento.
  Datas usam ISO 8601, mantendo o fuso quando existente.
- Textos maiores que 30000 unidades UTF-16 sao divididos em partes na aba
  `_textos_longos`. A celula original indica `@texto:aba:linha:campo`. Para
  recompor, filtrar aba/linha/campo e concatenar texto pela ordem de parte.
- Caracteres proibidos pelo XML do Excel sao representados reversivelmente por
  `JSON_TEXT:` seguido de uma string JSON. Isso nao altera o registro no banco.
- Valores que comecam com `=`, `+`, `-` ou `@` sao texto, nao formulas executaveis.
- Celulas vazias nao distinguem null de string vazia. Portanto, esse arquivo
  e uma exportacao de consulta/trabalho, NAO um backup restauravel ou importador.

## Escopo e limites

A allowlist reaproveita os campos de leitura da API e inclui classes, subclasses,
habilidades, recursos, antecedentes, essencias, tracos raciais, armadilhas e
conteudo editorial estatico. As tabelas de autenticacao, chaves, jogadores,
personagens e transacoes financeiras nao ficam expostas implicitamente.

Limites por arquivo: 12 tabelas, 10000 linhas por tabela, 50000 linhas totais,
500000 celulas e 32 MiB de texto. O erro pede para refinar a selecao; nao retorna
um arquivo truncado. Nao carrega todo o banco: consulta apenas colunas selecionadas
e percorre os resultados em blocos. O XLSX usa arquivo temporario ao ultrapassar
8 MiB em memoria. Nao ha dependencia nova: openpyxl ja estava nos requirements.

A previa assinada vale dez minutos e pertence ao usuario que a gerou. Edicoes na
selecao invalidam a previa na interface. O download revalida a selecao, os limites
e as contagens; mudanca de quantidade exige nova previa. Alteracoes de conteudo
que mantenham a contagem podem aparecer no arquivo: e uma consulta ao banco vivo,
nao uma garantia de snapshot imutavel entre previa e download.

Somente o log de auditoria do admin e gravado ao gerar um arquivo com sucesso.
Nenhum registro de catalogo e alterado. O log guarda modelos, campos e quantidades,
nao textos exportados ou credenciais. POSTs passam por CSRF do admin.

## Arquivos e verificacao

- `home/catalog_export.py`: politica de tabelas, validacao, filtros, previa e XLSX.
- `home/catalog_export_admin.py`: permissao, ticket, download e auditoria.
- `home/admin.py`: rota; `home/templates/admin/server_logs.html`: atalho.
- `home/templates/admin/catalog_export.html`: tela administrativa.
- `home/static/js/catalog-export.js`: selecao, filtros, previa e download.
- `home/static/css/admin/catalog-export.css`: layout responsivo.
- `home/test_catalog_export.py`: testes focados com banco descartavel.

Nao exige migration. Nao depende da migration de Epic Boon nem de qualquer acesso
a producao. Deploy futuro usa o fluxo normal de codigo/estaticos do site.
