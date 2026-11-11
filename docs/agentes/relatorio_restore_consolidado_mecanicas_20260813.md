# Restore consolidado de mecânicas — produção 2026-08-13

## Artefatos

- Backup usado como fotografia da produção: `backup_completo_20260813_184429.json`.
- Arquivo para upload: `ref/backups/restore_consolidado_mecanicas_20260813_184429.json`.
- Registros no arquivo: **5.095**, distribuídos em **21 modelos com dados**. O
  contrato contempla 23 modelos mecânicos; `TbConquista` e `TbArmadilha` estão
  vazios e, por isso, não aparecem no JSON.
- SHA-256: `21c666d501c2b4a49e91688df32db2968ba9407ccebb31fc5eb9e7d2ed962b7d`.
- Relatório técnico completo: `ref/backups/restore_consolidado_mecanicas_20260813_184429.report.json`.
- Evidência da simulação: `ref/backups/restore_consolidado_mecanicas_20260813_184429.simulation.json`.

Os arquivos em `ref/` são locais e não entram no Git. Este Markdown é o registro
versionável da leva.

## O que será alterado

| Modelo | Diferença em relação à produção |
|---|---:|
| Acessos de opção | 52 vínculos novos, principalmente opções de Artífice |
| Antecedentes | tags dos 30 registros |
| Bestiário oficial | 879 criaturas: 878 statblocks refinados e 1 ajuste adicional de tags |
| Classes | tags das 13 classes |
| Habilidades de classe | 27 registros: 21 ajustes de tags e 7 de descrição |
| Essências | imagens das 4 essências |
| Itens mágicos | 499 registros: nomes, slots, lojas e ajustes pontuais de tags/descrição |
| Linhagens | imagens das 16 linhagens |
| Magias | 201 registros: 156 ajustes de tags e 48 nomes em inglês |
| Opções de jogo | tags de 19 opções |
| Raças | imagens das 4 raças |
| Recursos de classe | 1 recurso novo: Magias Conhecidas do Paladino |
| Regras | 1 regra nova: Aumento de Atributo |
| Talentos | 47 registros: 45 descrições e 8 conjuntos de tags |
| Traços raciais | tags de 9 traços |

As quantidades de campos se sobrepõem: um mesmo registro pode ter mais de um campo
alterado.

### Correções deliberadas

- A habilidade **Maestria em Armas** do Paladino foi recuperada no catálogo local.
  A produção ainda tinha a entrada válida, mas com `swap:long_rest` duplicada. O
  resultado preserva a descrição e usa `pick:arma:2` com uma única troca por descanso
  longo.
- As 13 entradas abaixo deixam de ser tratadas como condições globais, pois eram
  efeitos específicos ou resíduos legados:
  `afastado`, `banido`, `doente`, `enlarge`, `frenesi`, `frenesi-de-sangue`,
  `in-receptaculo`, `incorporeo`, `marca-guardiao`, `possuido`, `queimando`,
  `seduzido` e `vibracoes-letais`.

## O que não será alterado

O arquivo não contém e o aplicador verifica por assinatura completa antes/depois:

- usuários, perfis, seguidores, curtidas e inventários de cosméticos;
- personagens e todas as escolhas, classes, itens, magias, perícias, recursos e
  talentos já gravados;
- ledger de aventuras, transações, missões, mercado, crônicas e jornal;
- regiões, territórios, organizações, camadas, marcadores e desenhos do mapa;
- textos institucionais editáveis no admin;
- criaturas e armadilhas criadas pela comunidade.

No bestiário, somente registros oficiais são atualizados. Os **920 IDs oficiais já
existentes** permaneceram iguais na simulação; criaturas novas receberiam IDs novos sem
colidir com conteúdo comunitário.

## Validações executadas

1. O backup completo foi carregado em um PostgreSQL temporário com todas as migrations.
2. O mesmo núcleo usado pelo painel `merge_conteudo` aplicou o arquivo de 5.095 linhas.
3. Memória de usuário/personagem ficou idêntica por contagem e SHA-256.
4. Mapa/wiki ficou idêntico por contagem e SHA-256.
5. Conteúdo comunitário ficou idêntico por contagem e SHA-256.
6. Os 920 IDs do bestiário oficial ficaram estáveis.
7. O catálogo resultante bateu semanticamente com a fonte local: 5.095/5.095,
   nenhuma chave ausente, extra, duplicada ou divergente.
8. `validate_tags --strict`: **0 erros**, nenhum verbo desconhecido. Permanecem 30
   avisos já catalogados de conjuração inata sem limite explícito.
9. Testes do restaurador/admin: **20 aprovados**.

## Ordem obrigatória em produção

1. Fazer um novo backup completo imediatamente antes do deploy e guardá-lo para
   rollback.
2. Publicar o código desta leva e executar as migrations. Isso instala o restaurador
   reforçado e os campos usados pelo fixture.
3. Conferir o SHA-256 do arquivo de upload.
4. No `admin/console`, abrir **Merge de conteúdo (dev -> produção)**.
5. Enviar `restore_consolidado_mecanicas_20260813_184429.json`.
6. **Não usar** o painel `Restauração de backup`, que trabalha por PK. O guard agora
   também recusa fixtures mecânicos ou de mundo nesse painel.
7. Confirmar no resultado as mensagens `MEMÓRIA INTACTA`, `MAPA/WIKI INTACTOS` e
   `CONTEÚDO COMUNITÁRIO INTACTO`.
8. Executar uma checagem rápida de Paladino, Artífice, magias, itens mágicos e uma
   criatura refinada.

## Rollback

Se o merge falhar, a transação inteira é revertida automaticamente. Para um problema
percebido depois da conclusão, usar o backup completo recém-gerado antes do deploy,
seguindo o procedimento de restauração integral da produção.
