# Restore consolidado de conteudo, wiki e mecanicas

- Arquivo: `C:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\backups\restore_consolidado_conteudo_wiki_mecanicas_20260709_135510.json`
- Backup real usado como referencia: `C:\Users\helio\Downloads\backup_completo_20260709_131415.json`
- Registros finais: 4064

## Fontes incluidas
- Mecanicas/conteudo: `C:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\backups\restore_patch_conteudo_20260630_201724.json` (2264 registros)
- Reparo estrutural sem mapa/wiki antigo: `C:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\backups\restore_reparo_tabelas_zeradas_conteudo_atual_20260630.json` (1644 registros)
- Wiki/lore/organizacoes: `C:\Users\helio\Desktop\Projetos Bonfas\BonfireSite-main\ref\backups\restore_lore_cidades_organizacoes_20260709_132014.json` (150 registros)
- Pins novos do backup real: 10 registros
- Correcao Montes Dorskal: 2 registros

## Contagem final por model
- `home.tbacessoopcao`: 97
- `home.tbbestiario`: 920
- `home.tbclasse`: 6
- `home.tbclassehabilidade`: 867
- `home.tbcondicao`: 27
- `home.tbidioma`: 22
- `home.tbitemmagico`: 954
- `home.tbitemmundano`: 302
- `home.tbmagia`: 36
- `home.tbmapmarker`: 5
- `home.tbopcaojogo`: 45
- `home.tborganizacao`: 81
- `home.tbrecompensamestre`: 9
- `home.tbrecursoclasse`: 131
- `home.tbregiao`: 64
- `home.tbregra`: 139
- `home.tbtalento`: 1
- `home.tbterritorio`: 6
- `home.tbtracoracial`: 352

## Remapeamento de PKs nulos
- `home.tbbestiario`: 892 registros `pk: null` remapeados para PKs do backup real

## Correcoes explicitas
- `TB_Regiao` pk 102: `Montes Dorksal` / `montes-dorksal` -> `Montes Dorskal` / `montes-dorskal`, com lore de `ref/Cidades/Areas-Selvagens/montes-dorskal.docx`.
- `TB_MapMarker` pk 146: `Montes Dorksal` -> `Montes Dorskal`, mantendo coordenadas e territorio do backup real.

## Observacoes
- O restaurador do admin faz upsert por PK e realinha sequences no PostgreSQL.
- As organizacoes exigem que o codigo/migracao da tabela `organizations` esteja em producao antes do restore.
- Nao inclui `TB_Regiao`, `TB_Territorio` nem `TB_MapMarker` do patch de reparo antigo, para nao sobrescrever o mapa novo.

## Sanitizacao contra models atuais
- Campos obsoletos removidos para o restaurador do admin aceitar o JSON:
  - `home.tbitemmundano`: ca (302), ca_base (302), ca_limite_des (302), dano (302), forca_minima (302), furtividade_desvantagem (302), maestria (302), propriedades (302), tipo_equip (302)
