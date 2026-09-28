# Operação Q07 — Ordem Primal

O conteúdo Bonfire importado define a escolha no nível 2 de Druida. A fixture
agora contém a escolha entre Xamã e Guardião e os efeitos descritos na habilidade.
Não altera nível, descrição, ID ou escolhas existentes.

Para um banco existente, primeiro conferir integridade e recuperação do backup,
identificar o banco alvo e a autorização de implantação. Nenhuma aplicação no
banco real foi realizada nesta entrega.

```powershell
venv/Scripts/python.exe manage.py repair_primal_order
```

A execução acima somente relata o antes/depois. Com os gates de implantação
satisfeitos, `--apply` grava as tags atomicamente. A reexecução não produz
alterações. O comando recusa habilidade ausente/duplicada, nível diferente de 2,
descrição divergente ou tags distintas das versões vazia/corrigida conhecidas.
Não substituir conteúdo divergente por esta fixture para contornar a recusa.

Após aplicação, conferir uma ficha de Druida2: uma opção de Ordem Primal,
Guardião com armas marciais/armadura média; Xamã com dois truques de Mago adicionais
associados ao Druida e bônus de Sabedoria (mínimo1) em Arcanismo/Religião.
Para retirar a mudança de serviço, suspender a edição de escolhas e restaurar a
versão de código/conteúdo do marco de implantação, preservando os registros de
escolhas e magias para reconciliação; não apagar esses registros.
