# Comparacao do backup 20260724_232711 com o PostgreSQL local

## Escopo

- Backup: `ref/backup_completo_20260724_232711.json`
- SHA-256: `326594B9791BC509709C10FFCB9C4B3670EAB12FBA1FC95473850F875B37A17B`
- Tamanho: 16.778.264 bytes
- Registros no backup: 6.682
- Modelos no backup: 47
- Banco local: PostgreSQL `postgres`, em `localhost:5432`
- Comparacao: contagem, chave natural e campos serializados. PK foi usada somente nos modelos sem chave natural segura.

O arquivo e valido: nao ha pares `model/pk` duplicados. O relatorio bruto esta em
`scratch/comparacao_backup_20260724_232711_vs_local.json`.

## Resultado executivo

O conteudo mecanico do backup e do PostgreSQL local e identico, campo a campo. Isso
inclui classes, habilidades de classe, recursos, subclasses, acessos, opcoes,
antecedentes, racas, tracos raciais, magias, talentos, itens, bestiario e regras.

As divergencias reais estao concentradas em:

1. Wiki e mapa: o backup e muito mais completo e mais recente que o banco local.
2. Dados vivos: usuarios, personagens, transacoes e dados do bot existem no backup,
   mas estao ausentes ou divergentes no ambiente local.
3. Dados internos do Django: permissoes, content types e sessoes locais nao pertencem
   ao backup e nao devem ser usados como sinal de divergencia de conteudo.

## Conteudo mecanico identico

| Modelo | Backup | Local | Resultado |
|---|---:|---:|---|
| Acessos a opcoes | 110 | 110 | Identico |
| Antecedentes | 30 | 30 | Identico |
| Bestiario | 920 | 920 | Identico |
| Classes | 13 | 13 | Identico |
| Habilidades de classe | 888 | 888 | Identico |
| Condicoes | 28 | 28 | Identico |
| Cosmeticos | 24 | 24 | Identico |
| Essencias | 4 | 4 | Identico |
| Idiomas | 22 | 22 | Identico |
| Itens magicos | 955 | 955 | Identico |
| Itens mundanos | 302 | 302 | Identico |
| Linhagens | 16 | 16 | Identico |
| Magias | 580 | 580 | Identico |
| Opcoes de jogo | 281 | 281 | Identico |
| Racas | 4 | 4 | Identico |
| Recompensas de mestre | 9 | 9 | Identico |
| Recursos de classe | 136 | 136 | Identico |
| Regras | 139 | 139 | Identico |
| Subclasses | 111 | 111 | Identico |
| Talentos | 139 | 139 | Identico |
| Tracos raciais | 352 | 352 | Identico |

`tbRecursosClasse` foi comparada pela chave composta
`(classe, subclasse, nome, nivel)`. O `slug` nao e globalmente unico nesse modelo;
usar somente o slug produziria um falso positivo.

O Bardo reworkado ja esta no backup e coincide integralmente com o banco local,
inclusive habilidades, recursos, subclasses, acessos e opcoes. Nao foi encontrada
uma copia mecanica antiga divergente entre esses dois bancos.

## Wiki e mapa

### Regioes

- Backup: 74
- Local: 23
- Ausentes no local: 51
- Presentes nos dois, mas alteradas: 21
- Campo alterado nas 21: `lore_markdown`
- Presentes e identicas: 2

Regioes ausentes no local:

`Arquipelago de Meraghos`, `Aurevalis`, `Bestarok`, `Caldeirao do Mar`,
`Campos de Umetsu`, `Castelo de Arendelle`, `Cume das Nevascas`,
`Deserto das Nagas`, `Deserto de Khurzahir`, `Deserto de Mahrenai`,
`Deserto Kobalico`, `Dharramir`, `Drakhaenor`, `Ecos de Vaurin`,
`Fenda Salgada`, `Ferlanden`, `Floresta dos Bordos`, `Geleiras Infinitas`,
`Hanryo`, `Ilha Udo`, `Kaldorae`, `Kear Vantor`, `Khazrundel`, `Kurohime`,
`Lunaris`, `Menaphos`, `Mizunaga`, `Montes Dorskal`, `Nehrasa`, `Nexovar`,
`Nexurith`, `Qassirah`, `Sairajah`, `Selat'Mura`, `Shi-no-mori`, `Skjoldrun`,
`Solcastros`, `Sophonemm`, `Sopro Invernal`, `Tarnubek`, `Tensai-nyo-ki`,
`Thamarezzin`, `Tremaynor`, `Tsurei`, `Vel Badran`, `Velmourn`, `Velquessar`,
`Vila Incandecente`, `Yokuyama`, `Zahrak` e `Zhelkar`.

Regioes cuja lore do backup diverge da local:

`Agrabbar`, `Auralon`, `Bastiao Rochaeterna`, `Brinvalde`, `Drumhuldar`,
`Elenharis`, `Elyrenna`, `Fjarnok`, `Floresta Eterna`, `Muralha de Agramar`,
`Porto Espolio`, `Shaerelyn`, `Solmarion`, `Sylvereth`, `Terras Devastadas`,
`Terras Ferteis`, `Velaryn`, `Vilaterra`, `Volgranndur`, `Vyrmhein` e
`Zar'Kantar`.

Em 17 dessas 21 regioes a lore local esta vazia. Nas quatro restantes, Agrabbar,
Auralon, Brinvalde e Velaryn, o texto do backup e maior que o local. O backup deve
ser tratado como a versao mais nova para wiki.

### Territorios

- Backup: 35
- Local: 9
- Ausentes no local: 26
- Presentes nos dois, mas alterados: 9
- Campos alterados: `coordenadas_poligono` em 7, `lore_markdown` em 4 e
  `cor_hex` em 1

Territorios ausentes no local:

`Arquivo das Rotas Cegas`, `Bairro das Lanternas Frias`, `Casa dos Contratos`,
`Cavernas de Cristal`, `Cavernas de Morada Baixa`,
`Cidades Escavadas da Faixa Central`, `Distrito das Bigornas Negras`,
`Docas Secas`, `Estacao das Correntes`, `Garganta dos Ferros Tortos`,
`Ilha da Noite`, `Mercado das Mil Cupulas`, `Mercado de Almas`, `Mercado Mudo`,
`Necropole`, `Nexovar`, `Posto Avancado Onirico`, `Praca das Correntes`,
`Reino Drakhar`, `Reino Thamar`, `Reino Tsunari`, `Salao das Correntes`,
`Territorio Aberrante`, `Territorio Miconideo`,
`Territorio Quenquem e Quitrino` e `Vulcao Pyrrak'Zul`.

Territorios alterados:

| Territorio | Campos |
|---|---|
| Floresta Eterna | coordenadas, cor |
| Reino Auraliano | coordenadas, lore |
| Reino de Agrabbar | coordenadas |
| Reino Eryndor | coordenadas |
| Reino Karag Dum | lore |
| Reino Volgran | lore |
| Territorio Independente | coordenadas |
| Vyrmrealm | coordenadas, lore |
| Zonas de Perigo | coordenadas |

### Marcadores e camadas

- Marcadores: backup 74, local 23.
- Ha 51 marcadores somente no backup.
- Dois marcadores existentes nos dois foram reposicionados no backup:
  `Auralon` (PK 10) e `Agrabbar` (PK 79).
- Camadas: quatro nos dois bancos; a camada PK 1 diverge somente em `publica`.
- Desenhos de mapa: um no backup (PK 3) e nenhum no local.

Os 51 marcadores ausentes correspondem as novas regioes do backup, incluindo
Solcastros, Ilha Udo, Aurevalis, Nexurith, Bestarok, Lunaris, Skjoldrun,
Geleiras Infinitas, Tensai-nyo-ki, Hanryo, Floresta dos Bordos, Tsurei,
Mizunaga, Yokuyama, Shi-no-mori, Kurohime, Tremaynor, Velmourn,
Vila Incandecente, Ferlanden, Nexovar, Zahrak, Sairajah, Dharramir, Nehrasa,
Tarnubek, Sophonemm, Drakhaenor, Deserto das Nagas, Thamarezzin, Vel Badran,
Selat'Mura, Qassirah, Deserto Kobalico, Menaphos, Zhelkar, Caldeirao do Mar,
Castelo de Arendelle, Sopro Invernal, Khazrundel, Kear Vantor, Kaldorae,
Fenda Salgada, Deserto de Khurzahir, Cume das Nevascas, Ecos de Vaurin,
Arquipelago de Meraghos, Velquessar, Deserto de Mahrenai, Campos de Umetsu e
Montes Dorskal.

### Organizacoes

- Backup: 81
- Local: 0

As 81 organizacoes existem somente no backup. A tabela existe localmente, mas
nao possui registros. Entre elas estao Academia de Lirandar, Academia dos Ventos,
Casa Real Auraliana, Conselho Mercantil Velaryn, Guilda da Ultima Esperanca,
Ordem da Vigilia, Sindicatos de Artifices, Sinodo de Karag Dum e Vigias do Veu.
A lista integral permanece disponivel no backup e no relatorio bruto.

## Dados vivos

Essas diferencas sao esperadas entre producao e desenvolvimento e nao devem ser
resolvidas sobrescrevendo o backup com o banco local.

| Modelo | Backup | Local | Diferenca principal |
|---|---:|---:|---|
| Usuarios | 24 | 14 | 10 ausentes; 9 alterados |
| Perfis | 23 | 11 | 12 ausentes; 11 alterados |
| Personagens | 12 | 0 | Todos ausentes localmente |
| Classes de personagem | 13 | 0 | Todos ausentes localmente |
| Escolhas de personagem | 82 | 0 | Todas ausentes localmente |
| Magias de personagem | 53 | 0 | Todas ausentes localmente |
| Talentos de personagem | 51 | 0 | Todos ausentes localmente |
| Itens de personagem | 39 | 0 | Todos ausentes localmente |
| Pericias de personagem | 69 | 0 | Todas ausentes localmente |
| Proficiencias de personagem | 63 | 0 | Todas ausentes localmente |
| Transacoes | 66 | 0 | Todas ausentes localmente |

O backup tambem tem mais dados do bot: 228 logs de personagem contra 214 locais,
353 missoes contra 321, 87 transacoes contra 83, 63 membros contra 62 e 53 ranks
contra 47. Alguns registros comuns tambem mudaram desde a copia local.

## Conclusao operacional

1. Nao ha mudanca mecanica local a exportar para esse backup: os modelos mecanicos
   comparados ja sao identicos.
2. Para atualizar o PostgreSQL local, a direcao segura para wiki, mapa,
   organizacoes, personagens e dados de usuario e **backup -> local**.
3. Nao use uma restauracao local completa sobre producao: isso apagaria 51
   regioes, 26 territorios, 51 marcadores, 81 organizacoes, 12 personagens e
   outros dados vivos.
4. Qualquer sincronizacao futura deve manter politicas separadas:
   mecanicas por chave natural; wiki/mapa preservando a versao mais nova; memoria
   e usuarios apenas por restauracao completa explicitamente autorizada.
