# QA do redesign em DEV

Executar após o responsável atualizar o ambiente DEV a partir do commit
publicado em `dev`. O push do Git não comprova que o site/API foi atualizado.
Registrar URL, SHA servido (quando disponível), data e conta de teste por
referência ao cofre; não colocar credenciais no relatório.

## Percurso funcional

1. Em `/sistemas/pathbuilder/`, percorrer uma classe/subclasse de cada grupo da
   [matriz S10](redesign-s10-aceite.md), inclusive progressão 1/20 e as ordens
   do Caçador quando publicadas no catálogo do ambiente. Confirmar que a prévia
   não cria ficha nem mostra personagens de outra conta. Registrar separadamente
   qualquer conteúdo canônico ainda ausente no catálogo DEV.
2. Com conta QA, abrir ficha existente e criação de ficha; confirmar dados,
   permissões, legado e navegação por teclado. Conferir mercado mundano/mágico,
   compra e venda em dados de teste, revisão antes da confirmação, carteira e
   inventário. Conferir oficina, seleção de personagem e histórico do navegador.
3. Conferir páginas públicas, referência, perfil de mestre, anúncios moderados,
   comunidade e cosméticos. Na revisão de `/colaborador/`, cancelar e reabrir
   antes de confirmar; conferir conta e valor. Pagamentos/OAuth somente em
   sandbox, sem compra real.
4. Repetir navegação e formulários principais com teclado e larguras de 360,
   390, 768, 1024 e 1440 px. Verificar foco visível, ausência de rolagem
   horizontal global, controles acessíveis e imagens carregadas. Comparar o
   Pathbuilder com as cinco capturas em `evidencias/s10/`.

Relatar cada falha com rota, largura, conta QA por alias, passos, resultado
esperado/obtido e captura. Não enviar perfis de teste no catálogo de produção.
O guia de [release e reversão](redesign-release-reversao.md) mantém G01/G02,
backup e rollback separados deste QA. Produção só é verificada em S13 após G02.
