# Restore da Oficina de Magia - 2026-08-18

## Arquivos

- Base de comparação: `C:\Users\helio\Downloads\backup_completo_20260817_235225.json`
- Restore: `ref/backups/restore_consolidado_oficina_magia_20260818.json`
- Relatório técnico: `ref/backups/restore_consolidado_oficina_magia_20260818.report.json`
- SHA-256 do restore: `0f05471f9a7c920c4335db1c4d8095bb44edd6cd019f660b128b11d25aee105d`

## Ordem obrigatória na produção

1. Publicar o código desta entrega.
2. Executar as migrations, incluindo `home.0098_spell_access_and_transcription_requests`.
3. No console administrativo, aplicar o JSON acima pela ação `merge_conteudo`.

O restore não deve ser aplicado antes da migration: as magias passam a possuir a
coluna `ClassesSlugs`, e os pedidos entre grimórios usam a nova tabela
`TB_SolicitacaoTranscricao`.

## Diferenças contra a produção

- `home.tbmagia`: 580 registros recebem somente `classes_slugs`, mantendo o texto de `classes` já existente na produção.
- `home.tbclassehabilidade`: 10 tags alteradas, correspondentes a Escolas de Foco do Mago e ao custo por círculo do Místico.
- `home.tbopcaojogo`: 8 Escolas de Foco novas.

A divergência editorial de `Dom da Alacridade` foi conciliada antes da geração:
o acesso de Mago existente na produção foi preservado no banco local e no restore.

## Garantias da simulação

- 5.103 registros desserializados com sucesso.
- Nenhuma tabela de memória de jogador incluída ou alterada.
- Mapa e wiki da produção preservados.
- Conteúdo comunitário preservado.
- Merge em duas passagens validado; `TbArmadilha` permaneceu fora da segunda passagem conforme a política atual do sincronizador.
