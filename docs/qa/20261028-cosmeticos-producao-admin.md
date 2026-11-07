# Cosmeticos de teste publicados em producao

## Autorizacao e execucao

PO autorizou ativar os itens de teste em producao, sem uso por jogadores
comuns. Execucao pelo admin autenticado de bonfiretales.com.br, usando
formularios existentes; sem SQL, shell remoto, migration ou alteracao de PK.

Oito registros foram criados ativos com origem `staff`, sem preco/plano e
sem oferta comercial, resgate ou conquista automatica:

| PK | Slug |
| --- | --- |
| 54 | tema-lua-vermelha |
| 55 | tema-lua-negra |
| 56 | tema-lua-cristal |
| 57 | moldura-lua-vermelha |
| 58 | moldura-lua-negra |
| 59 | moldura-lua-cristal |
| 60 | moldura-vigilia-das-lanternas |
| 61 | tema-vigilia-das-lanternas |

Catalogo passou de 49 para 57 registros. Linhas e links/identidades dos
49 anteriores comparados antes/depois e preservados. Manifestos de producao
responderam 200 e ja apontavam para Sangue v5, Negra/Cristal v6.

## Liberacao restrita de inventario

Selecionadas exclusivamente as sete contas existentes com `is_superuser=1`,
todas tambem com `is_staff=True`. Nenhuma permissao de conta foi alterada.
Criados 56 inventarios (oito por conta), origem `staff`, sem suspensao.
Cada formulario confirmou destinatario/item antes de salvar e mensagem de
sucesso depois. Nao houve concessao a usuarios comuns.

Conferencia remota por busca do inventario: 42 linhas lunares + 14 da Vigilia,
todas pertencentes aos sete administradores identificados. No perfil Gaz,
os quatro temas e as quatro molduras aparecem habilitados. A aparencia
equipada nao foi modificada, nem o perfil salvo.

## Limite do mecanismo existente

`staff` e origem de concessao, NAO um bypass automatico por cargo.
A restricao atual e mantida pela lista de inventarios: somente os admins
receberam os oito itens; catalogo ativo nao os torna livres.
Nao foi implantado um novo bloqueio dinamico por cargo: uma futura retirada
de permissao de admin deve incluir a suspensao desses inventarios de teste.
Novos admins precisam de concessao; durante QA nao conceder a contas comuns.
A liberacao manual para jogadores apos QA continua sendo uma acao separada.

Nenhuma nova oferta, cobranca ou grant automatico foi criado. Este registro
comprova publicacao e acesso administrativo atual, nao aceite artistico final
nem teste exaustivo de todas as combinacoes em ficha.
