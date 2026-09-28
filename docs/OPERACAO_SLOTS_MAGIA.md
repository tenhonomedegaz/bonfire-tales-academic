# Slots de magia — contrato e operação (Q02)

Implementação da seção 5.3 de `ARQUITETURA_EVOLUCAO_BONFIRE.md` para
consumir/devolver slots. Os demais comandos parciais continuam no plano integral.

## Contrato

- O POST identifica o personagem na rota e exige dono ou staff, sessão e CSRF.
- `nivel`, `acao`, `expected_version` e `operation_id` identificam o comando.
  Os formulários renderizados possuem esses campos mesmo com o cliente desligado.
- O servidor deriva o teto, bloqueia o personagem e compara a versão antes de
  alterar o recurso. Mutação e recibo são gravados na mesma transação PostgreSQL.
- A versão inclui identidade do recurso, contador, teto e revisão persistida;
  gasto, recuperação e descanso invalidam versões anteriores quando mudam o estado.
- Repetir a operação original não gasta novamente. A resposta informa o contador
  atual, inclusive se houve outro comando ou descanso depois da primeira aplicação.
- Reusar uma chave com dados diferentes resulta em `409 operation_conflict`.
  Versão antiga resulta em `409 stale_version`, com snapshot para reconciliação.
- A identidade canônica (`spell_slot:1`, por exemplo) prevalece sobre o nome de
  apresentação. Recursos legados sem chave são promovidos sem repor gastos.
  Mudança de teto conserva a quantidade gasta, inclusive na projeção sem escrita.
- O navegador atualiza cartão e resumo do círculo pelo mesmo snapshot e mantém
  aba, foco e rolagem. Falha de rede/timeout não dispara retry automático: a ação
  anterior fica disponível para reconciliar usando a mesma chave de operação.
  O timeout cobre tanto cabeçalhos quanto leitura do corpo JSON.

## Implantação e recuperação

A migração `0103_resource_command_receipts` adiciona `Versao` a
`TB_PersonagemRecurso` e cria `TB_OperacaoRecurso`. Até esta etapa, os ensaios e
testes foram feitos exclusivamente em PostgreSQL isolado; este documento não
autoriza aplicar a migração ou publicar em produção.

Antes de implantar no banco alvo, verificar integridade, backup recuperável,
compatibilidade dos consumidores que compartilham as tabelas e autorizações
existentes. Registrar o banco/cluster e resultado do ensaio de restauração.
Não usar reversão para 0102 como procedimento de recuperação: ela elimina os
recibos e a proteção contra repetição de operações já realizadas.

Para desligar somente o cliente parcial, definir `SPELL_SLOT_PARTIAL_ENABLED=0`
e recarregar a aplicação. Novas páginas usam formulários HTML com os mesmos
campos de versão/operação e retorno `?aba=magias`. Clientes antigos recebem
`503 disabled` e recarregam a página sem reenviar o POST automaticamente.
Preservar a migração, os recursos e os recibos durante esse desligamento.

`TbOperacaoRecurso` é memória do usuário na classificação de `deploy_sync`.
Não deve ser substituída por importação de conteúdo nem por restauração de uma
build de personagem. Não existe política autorizada de expiração desses recibos.

## Evidências e limites

- `home/test_resource_commands.py`: autorização, CSRF, limites, rollback,
  idempotência, versões, mudança de teto, legado, restauração de build e
  concorrência em conexões PostgreSQL distintas.
- `home/test_resource_command_migration.py`: upgrade de contador legado e
  reexecução, em banco de testes; não é roteiro de downgrade de produção.
- `home/js_tests/spell_slots.browser.cjs`: nove cenários Chromium controlados.
- `home/test_spell_slots_e2e.py` e `home/js_tests/spell_slots.e2e.cjs`: fluxo real
  Django/PostgreSQL/Chromium, duas abas, reload e alternativa HTML.
- Resultados executados, artefatos e pendências de aceite são registrados em
  `docs/EVOLUCAO_PROGRESSO.md`. A existência destes testes não prova aprovação.

Formulários antigos sem versão ou chave de operação pedem atualização da ficha
sem efetuar gasto. Integrações devem enviar ambos os campos. O restante da ficha e os demais
fluxos parciais não recebem automaticamente as garantias específicas de Q02.

## Reparo de conteúdo Q04 — Clérigo

`python manage.py repair_cleric_slots` exibe a prévia JSON sem alterar conteúdo.
Após conferir banco alvo, backup recuperável e autorização de implantação,
`python manage.py repair_cleric_slots --apply` aplica todo o lote na mesma transação.
O comando não é executado automaticamente na inicialização nem nesta entrega no
banco real. Divergência de tabela, ausência ou duplicidade interrompe o lote inteiro.

Escopo: recursos de classe do Clérigo, sem subclasse, importados com slugs `1`–`9`.
Eles passam ao protocolo `1o`–`9o` já reconhecido pelo motor; o 5º círculo recebe
`18:3`, conforme Q04 da arquitetura. IDs, referências e contadores de personagens
são preservados. Tabelas já corrigidas são aceitas; reexecução não altera nada.
A fixture `home/fixtures/conteudo.json` contém o mesmo resultado, impedindo que
nova carga dessa fonte reintroduza o erro. O resolvedor compartilhado não mudou.

Os demais marcos da tabela importada foram preservados e conferidos em 1–20.
Em particular, o 2º círculo no nível 5 continua em 4, como no conteúdo existente;
isso não é aprovação editorial dessa anomalia nem substituição por regra externa.
Uma correção adicional requer sua própria referência. O reparo recusa tabelas
divergentes para não sobrescrever uma revisão local desconhecida.

Leituras projetam o novo teto sem escrita. No próximo comando, o motor conserva
a quantidade já gasta: de 1/2 para teto 3, a prévia mostra 2/3; gastar resulta em
1/3. A alternativa HTML e o cliente parcial usam esse mesmo cálculo.
O desligamento do cliente parcial descrito acima continua disponível e não
reverte conteúdo nem elimina recibos. Não reduzir tetos como forma de rollback
sem examinar gastos e versões em uso.

Evidências regionais: `scratch/evolucao-q04/regional.txt` (4/4, progressão 1–20,
prévia/reexecução/conflitos e ficha/consumo em 18–20) e `e2e.txt` (1/1, três gastos,
limite, reload e contadores em Chromium/Django/PostgreSQL). Capturas 1280/360 em
`scratch/evolucao-q04/visual/`. Ensaios exclusivamente no banco de testes.
