{
  "output": "ref\\backups\\restore_consolidado_conteudo_20260816_171614.json",
  "gerado_em": "20260816_171623",
  "fonte": "DEV (postgresql) via ORM",
  "aplicador_recomendado": "admin console -> acao 'merge_conteudo' (home.deploy_sync.sincronizar_conteudo)",
  "base_analise": "C:\\Users\\helio\\Downloads\\backup_completo_20260816_142742.json",
  "rollback": "C:\\Users\\helio\\Downloads\\backup_completo_20260816_142742.json",
  "principio": "CONTEUDO dev-vence; MAPA/MUNDO prod-vence; MEMORIA ausente.",
  "final_records": 5095,
  "sha256_arquivo": "e731f3539b363781d1651dcff053c414267e66c298c52eaa051c72b453b7c929",
  "comparacao_baseline": {
    "arquivo": "C:\\Users\\helio\\Downloads\\backup_completo_20260816_142742.json",
    "modelos_com_diferenca": {
      "home.tbclasse": {
        "alterados": 1,
        "inseridos": 0,
        "somente_na_producao": 0,
        "acao_somente_na_producao": "preservados_por_upsert",
        "campos_alterados": {
          "tags_json": 1
        },
        "exemplos_alterados": [
          "slug:paladino"
        ],
        "exemplos_inseridos": [],
        "exemplos_somente_na_producao": []
      },
      "home.tbclassehabilidade": {
        "alterados": 155,
        "inseridos": 0,
        "somente_na_producao": 0,
        "acao_somente_na_producao": "removidos_por_substituicao",
        "campos_alterados": {
          "descricao": 151,
          "tags_json": 12
        },
        "exemplos_alterados": [
          "id_classe=artifice|id_subclasse=None|niveladquirido=1|nome=Conjuração de Magias",
          "id_classe=artifice|id_subclasse=alquimista|niveladquirido=3|nome=Elixires Alquímicos",
          "id_classe=artifice|id_subclasse=engenheiro-de-construto|niveladquirido=15|nome=Especialização de Núcleo",
          "id_classe=artifice|id_subclasse=engenheiro-de-construto|niveladquirido=5|nome=Ataque Reativo",
          "id_classe=artifice|id_subclasse=ferreiro-de-batalha|niveladquirido=5|nome=Ataque Extra Mágico",
          "id_classe=artifice|id_subclasse=magiduelista|niveladquirido=15|nome=Mestre Magiduelista",
          "id_classe=barbaro|id_subclasse=None|niveladquirido=20|nome=Avatar da Fúria",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=10|nome=Magia Instável",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=14|nome=Caos Encarnado",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=18|nome=Golpe Dissipador",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=3|nome=Faro Arcano",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=3|nome=Magia Selvagem",
          "id_classe=barbaro|id_subclasse=caminho-da-feiticaria-selvagem|niveladquirido=6|nome=Ruptura Arcana",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=10|nome=Égide Primordial",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=14|nome=Despertar Rúnico",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=18|nome=Campeão das Runas",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=3|nome=Runas Elementais",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=6|nome=Armamento Rúnico Aprimorado",
          "id_classe=barbaro|id_subclasse=caminho-do-arauto-runico|niveladquirido=6|nome=Essência Rúnica Entrelaçada",
          "id_classe=barbaro|id_subclasse=caminho-do-berserker|niveladquirido=10|nome=Presença Intimidante"
        ],
        "exemplos_inseridos": [],
        "exemplos_somente_na_producao": []
      },
      "home.tbitemmagico": {
        "alterados": 12,
        "inseridos": 0,
        "somente_na_producao": 0,
        "acao_somente_na_producao": "preservados_por_upsert",
        "campos_alterados": {
          "descricao_markdown": 3,
          "detalhes_sintonizacao": 10,
          "preco": 1,
          "raridade": 1,
          "tags_json": 4
        },
        "exemplos_alterados": [
          "slug:amuleto-da-saude",
          "slug:armadura-mizzium",
          "slug:cinto-da-forca-do-gigante-da-colina",
          "slug:cinto-da-forca-do-gigante-de-gelo",
          "slug:cinto-da-forca-do-gigante-de-pedra",
          "slug:cinto-da-forca-gigante-da-tempestade",
          "slug:cinto-da-tempestade-desperto",
          "slug:cinto-da-tempestade-exaltado",
          "slug:cinto-de-fogo-forca-gigante",
          "slug:cinturao-da-tempestade-dormente",
          "slug:pocao-de-invulnerabilidade",
          "slug:tiara-do-intelecto"
        ],
        "exemplos_inseridos": [],
        "exemplos_somente_na_producao": []
      },
      "home.tbrecursoclasse": {
        "alterados": 0,
        "inseridos": 9,
        "somente_na_producao": 9,
        "acao_somente_na_producao": "removidos_por_substituicao",
        "campos_alterados": {},
        "exemplos_alterados": [],
        "exemplos_inseridos": [
          "id_classe=artifice|id_subclasse=None|slug=magias_preparadas|nivel=None",
          "id_classe=bardo|id_subclasse=None|slug=magias_conhecidas|nivel=1",
          "id_classe=clerigo|id_subclasse=None|slug=magias_preparadas|nivel=None",
          "id_classe=feiticeiro|id_subclasse=None|slug=magias_conhecidas|nivel=None",
          "id_classe=guerreiro|id_subclasse=cavaleiro-arcano|slug=magias_conhecidas|nivel=None",
          "id_classe=ladino|id_subclasse=trilha-do-trapaceiro-arcano|slug=magias_preparadas|nivel=None",
          "id_classe=mistico|id_subclasse=None|slug=magias_conhecidas|nivel=None",
          "id_classe=mistico|id_subclasse=None|slug=truques_conhecidos|nivel=None",
          "id_classe=paladino|id_subclasse=None|slug=magias_preparadas|nivel=None"
        ],
        "exemplos_somente_na_producao": [
          "id_classe=artifice|id_subclasse=None|slug=magias-conhecidas|nivel=None",
          "id_classe=bardo|id_subclasse=None|slug=magias-conhecidas|nivel=1",
          "id_classe=clerigo|id_subclasse=None|slug=magias-conhecidas|nivel=None",
          "id_classe=feiticeiro|id_subclasse=None|slug=magias-conhecidas|nivel=None",
          "id_classe=guerreiro|id_subclasse=cavaleiro-arcano|slug=magias-preparadas|nivel=None",
          "id_classe=ladino|id_subclasse=trilha-do-trapaceiro-arcano|slug=magias-preparadas|nivel=None",
          "id_classe=mistico|id_subclasse=None|slug=magias-conhecidas|nivel=None",
          "id_classe=mistico|id_subclasse=None|slug=truques-conhecidos|nivel=None",
          "id_classe=paladino|id_subclasse=None|slug=magias-conhecidas|nivel=None"
        ]
      },
      "home.tbtalento": {
        "alterados": 3,
        "inseridos": 0,
        "somente_na_producao": 0,
        "acao_somente_na_producao": "preservados_por_upsert",
        "campos_alterados": {
          "pre_requisito": 3
        },
        "exemplos_alterados": [
          "slug:linguista",
          "slug:mestre-de-escudo",
          "slug:mestre-pistoleiro"
        ],
        "exemplos_inseridos": [],
        "exemplos_somente_na_producao": []
      }
    },
    "chaves_duplicadas_producao": {},
    "chaves_duplicadas_dev": {},
    "renomeacoes_de_slug": [
      {
        "modelo": "home.tbitemmagico",
        "pk_producao": 404,
        "slug_antigo": "Tiara-do-Intelecto",
        "slug_novo": "tiara-do-intelecto"
      }
    ],
    "politica": {
      "upsert": [
        "home.tbantecedente",
        "home.tbclasse",
        "home.tbconquista",
        "home.tbcosmetico",
        "home.tbessencia",
        "home.tbitemmagico",
        "home.tbitemmundano",
        "home.tblinhagem",
        "home.tbmagia",
        "home.tbopcaojogo",
        "home.tbraca",
        "home.tbsubclasse",
        "home.tbtalento"
      ],
      "substituicao": [
        "home.tbacessoopcao",
        "home.tbarmadilha",
        "home.tbbestiario",
        "home.tbclassehabilidade",
        "home.tbcondicao",
        "home.tbidioma",
        "home.tbrecompensamestre",
        "home.tbrecursoclasse",
        "home.tbregra",
        "home.tbtracoracial"
      ]
    }
  },
  "por_tabela": {
    "home.tbraca": {
      "modelo": "TbRaca",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 4,
      "contagem_esperada_pos_aplicacao": 4,
      "sha256_registros": "4307faecb5bb135d7eaa1435425b4c63a02b50e33dd07e6a7fbf1d986e8e0bb7"
    },
    "home.tbessencia": {
      "modelo": "TbEssencia",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 4,
      "contagem_esperada_pos_aplicacao": 4,
      "sha256_registros": "8eb1e4f09dd7a610cbf3411ea8cfa5967a5223d96ba229ff200aadb650153a6f"
    },
    "home.tbantecedente": {
      "modelo": "TbAntecedente",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 30,
      "contagem_esperada_pos_aplicacao": 30,
      "sha256_registros": "6490c1f9600dec818a705ed298a192cf9ae861f351824cebec3ec07dfeb0b0e8"
    },
    "home.tbclasse": {
      "modelo": "TbClasse",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 13,
      "contagem_esperada_pos_aplicacao": 13,
      "sha256_registros": "b075d8c530e0947138d0a2a85be13eeaa6a736cb2b233074dcb25d7201447c2d"
    },
    "home.tbopcaojogo": {
      "modelo": "TbOpcaojogo",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 281,
      "contagem_esperada_pos_aplicacao": 281,
      "sha256_registros": "ec6cf7b8144af08abfd89d70c8db0e553782ef51b01db96d7dd6bc3e3987252d"
    },
    "home.tbmagia": {
      "modelo": "TbMagia",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 580,
      "contagem_esperada_pos_aplicacao": 580,
      "sha256_registros": "87145957f486b492fc4f4c36ecf742f4ebbaf4bb82373f7fa61a0113e350c75f"
    },
    "home.tbtalento": {
      "modelo": "TbTalento",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 139,
      "contagem_esperada_pos_aplicacao": 139,
      "sha256_registros": "4f93afce379095f854cbc290bb308d42bd7003a1e9720a626d943c0f57db06c5"
    },
    "home.tbitemmundano": {
      "modelo": "TbItemMundano",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 302,
      "contagem_esperada_pos_aplicacao": 302,
      "sha256_registros": "2a223c0b2c862c57cb6d4921daff68f7c6366a842a9203c9ec662244c8e1bafb"
    },
    "home.tbitemmagico": {
      "modelo": "TbItemMagico",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 946,
      "contagem_esperada_pos_aplicacao": 946,
      "sha256_registros": "180a8c717ef0987e836dfd21de013e56d383b83012a9a6be7f200879176e530b"
    },
    "home.tblinhagem": {
      "modelo": "TbLinhagem",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 16,
      "contagem_esperada_pos_aplicacao": 16,
      "sha256_registros": "d303323d77d7d0b0d9309ddd42cc73ffc06abad01191c8ae8377f6a29d1c4459"
    },
    "home.tbsubclasse": {
      "modelo": "TbSubclasse",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 111,
      "contagem_esperada_pos_aplicacao": 111,
      "sha256_registros": "ea80e8ed6a1dc061cb0114041e45b427cc294f1668e30d8b4a2330ec548fa8b2"
    },
    "home.tbcosmetico": {
      "modelo": "TbCosmetico",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 24,
      "contagem_esperada_pos_aplicacao": 24,
      "sha256_registros": "3225554d3dfbf33ac86d46eaebbf7caa253da2e790c54a1316ddd68a8106439d"
    },
    "home.tbconquista": {
      "modelo": "TbConquista",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "0 no arquivo: modelo ausente no fixture e preservado na prod."
    },
    "home.tbclassehabilidade": {
      "modelo": "TbClassehabilidade",
      "acao": "substitui",
      "linhas_no_arquivo": 889,
      "contagem_esperada_pos_aplicacao": 889,
      "sha256_registros": "fb6f8c2799c36ce1203114d0e54f124ee8836439527ecddeb1ebddc27c73b5ef"
    },
    "home.tbrecursoclasse": {
      "modelo": "TbRecursoclasse",
      "acao": "substitui",
      "linhas_no_arquivo": 136,
      "contagem_esperada_pos_aplicacao": 136,
      "sha256_registros": "25f5e71af5edfc34dd6db2adf59d3e3c35aff4b3be0d7d2067e775b2afe66e04"
    },
    "home.tbacessoopcao": {
      "modelo": "TbAcessoopcao",
      "acao": "substitui",
      "linhas_no_arquivo": 162,
      "contagem_esperada_pos_aplicacao": 162,
      "sha256_registros": "46512de62c4936db7ca79d7c23f254a32f92e6ed234759f66e56cb2cf312ad1d"
    },
    "home.tbtracoracial": {
      "modelo": "TbTracoracial",
      "acao": "substitui",
      "linhas_no_arquivo": 352,
      "contagem_esperada_pos_aplicacao": 352,
      "sha256_registros": "3f5ebd0904ebecd0150fa3b5f7c58d47cef864bd9b05310bfb40462d41f98021"
    },
    "home.tbcondicao": {
      "modelo": "TbCondicao",
      "acao": "substitui",
      "linhas_no_arquivo": 15,
      "contagem_esperada_pos_aplicacao": 15,
      "sha256_registros": "df0b9946940a03807044063dc4720ddab67de3b77a981a64c297447354992008"
    },
    "home.tbidioma": {
      "modelo": "TbIdioma",
      "acao": "substitui",
      "linhas_no_arquivo": 22,
      "contagem_esperada_pos_aplicacao": 22,
      "sha256_registros": "6326fd758f47a7d2946e290f6784eb478b712a44acd31c82b6747537a13c105c"
    },
    "home.tbregra": {
      "modelo": "TbRegra",
      "acao": "substitui",
      "linhas_no_arquivo": 140,
      "contagem_esperada_pos_aplicacao": 140,
      "sha256_registros": "f62ad22865ae245a0b91a86b8e95b554f041158dd4ea7eb2a8b14d5f3dea420b"
    },
    "home.tbrecompensamestre": {
      "modelo": "TbRecompensaMestre",
      "acao": "substitui",
      "linhas_no_arquivo": 9,
      "contagem_esperada_pos_aplicacao": 9,
      "sha256_registros": "05a1fcc4f595265d473ae6cae2b5b9a29298f4a51795f28eb7c880433f300f0c"
    },
    "home.tbbestiario": {
      "modelo": "TbBestiario",
      "acao": "substitui_oficiais_preserva_comunidade",
      "linhas_no_arquivo": 920,
      "contagem_esperada_pos_aplicacao": 920,
      "sha256_registros": "a8ff32c094bc3d6f923582ef06e4b0f7a71a346fee369c9857bbd26beb102358"
    },
    "home.tbarmadilha": {
      "modelo": "TbArmadilha",
      "acao": "substitui_oficiais_preserva_comunidade",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "0 no arquivo: modelo ausente no fixture e preservado na prod."
    },
    "home.tbmaplayer": {
      "modelo": "TbMapLayer",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 4,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    },
    "home.tbregiao": {
      "modelo": "TbRegiao",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 23,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    },
    "home.tbterritorio": {
      "modelo": "TbTerritorio",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 9,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    },
    "home.tborganizacao": {
      "modelo": "TbOrganizacao",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    },
    "home.tbmapmarker": {
      "modelo": "TbMapMarker",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 23,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    },
    "home.tbmapdesenho": {
      "modelo": "TbMapDesenho",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/wiki da producao e preservado."
    }
  },
  "validacao": {
    "deserialize_records": 5095,
    "merge_mem_ok": true,
    "merge_prod_preservada_ok": true,
    "merge_comunidade_ok": true,
    "merge_pass2_skipped": [
      "TbArmadilha"
    ],
    "memory_models_in_fixture": [],
    "production_preserved_models_in_fixture": [],
    "line_endings": "CRLF",
    "bom": true
  }
}
