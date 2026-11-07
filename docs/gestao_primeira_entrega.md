# Central de Gestao: primeira entrega

Estado: implementada em DEV. Nao substitui ainda todos os dominios do admin.
Referencia: [arquitetura](planos/20261106-central-gestao.md).

## Fluxo disponivel

`/gestao/` -> Pessoas -> Jogador -> Cosmeticos -> Conceder.

- Cabecalho do site, navegacao na mesma guia, busca por conta/nome/Discord.
- E-mail pesquisavel/exibido somente para Administrador nesta primeira entrega.
- Resumo da conta e cargos em nomes humanos, sem seletor de centenas de Permissions.
- Inventario com miniatura, origem, suspensao e direitos pagos/permanentes separados.
- Catalogo por tipo/busca, selecao, motivo, previa de destinatario/item e confirmacao.
- Recibo com autor, motivo, resultado e identificador; reenviar a mesma confirmacao
  retorna o recibo anterior, sem duplicar inventario.
- Compra/conquista existente nao tem sua origem sobrescrita. Direito permanente
  nao e removido. Item suspenso nao e reativado implicitamente.
- Nenhuma cobranca ou alteracao de saldo e feita pela concessao manual.
- Busca/cancelamento preservam parametros conhecidos, sem aceitar URL externa de retorno.
- Consulta pela Central nao cria perfis ausentes. Datas usam Brasilia somente na
  renderizacao, sem alterar o fuso das outras telas.

## Acesso

Usuario ativo com `is_superuser` tem acesso, sem exigir `is_staff` nesta Central.
Outros acessos exigem Permissions explicitas, herdadas ou individuais:

| Capacidade | Permission |
| --- | --- |
| Consultar pessoas | `home.view_management_people` |
| Consultar inventario | `home.view_management_cosmetics` |
| Conceder item manual | `home.grant_management_cosmetic` |

Concessao exige as tres. Ter apenas `is_staff`, badge, rank ou cargo de mestre
nao libera a tarefa. Nenhuma conta foi promovida e nenhuma atribuicao de Group
recebeu novas Permissions automaticamente.

## Persistencia e publicacao

Migration `0172_manual_cosmetic_grant_receipt` cria somente a estrutura generica de
recibos e suas Permissions. Nao altera `auth_user`, jogadores, saldos ou catalogos.
Nao ha migration por cosmetico, rank, classe, mestre ou missao.

A instalacao segue o `/site-update` monitorado (pull, migrations, estaticos e restart).
Sem chave nova, alteracao de env ou comando manual separado para esta entrega.
Conferir a rota, um fluxo autorizado e uma recusa apos o lote ser instalado.

Arquivos: `home/gestao/` (policy, servico, forms, queries/views e rotas),
`home/gestao_models.py`, migration 0172, templates `home/gestao/`, CSS/JS da pagina,
integracao em urls/context processor/header e `home/test_gestao.py`.

## O que continua pendente

- Matriz e editor de cargos/acesso efetivo para Staff/Rulesmaster/Loremaster/Jornalista.
- Retirada **fisica** de `is_staff` e troca/adocao de modelo de conta, conforme ensaio.
- Retracao de concessao manual e representacao completa de todas as fontes revogaveis.
- Demais areas: regras/publicacao, mundo, comunidade, economia e operacao tecnica.
- Retirada definitiva das telas antigas. O admin tecnico ainda existe para os
  dominios nao migrados; esta entrega nao e uma troca de CSS daquele painel.

O novo recibo nao representa uma segunda carteira nem um novo sistema de direito
permanente. O inventario e os comprovantes existentes continuam fontes de verdade.

## Evidencia local desta entrega

- Quinze verificacoes focadas de acesso, previa, recibo, repeticao, CSRF, preservacao
  de compra, consulta sem escrita e horario passaram em SQLite descartavel.
- Modelos e migration compativeis: nenhuma alteracao adicional gerada pelo Django.
- Fluxo real de navegador conferido em 390 e 1440 px, incluindo confirmacao,
  recibo e inventario; sem corte horizontal, imagens ausentes ou erro de JavaScript.
- Capturas e resultados locais em
  `%LOCALAPPDATA%/BonfireQA/management-preview-20261106/`.
- Previa isolada em `http://127.0.0.1:8777/gestao/`, com dados ficticios. Nao e
  prova de instalacao ou concessao em producao.

Entrega local preparada para publicacao na `dev`. A instalacao em producao
continua dependendo do `/site-update` apos o envio; commit e push nao instalam
as telas nem aplicam concessoes ou dados financeiros.
