{
  "output": "ref\\backups\\restore_consolidado_bardo_rework_limpo_20260724_191215.json",
  "gerado_em": "20260724_192550",
  "fonte": "DEV (postgresql) via ORM",
  "aplicador_recomendado": "admin console -> acao 'merge_conteudo' (home.deploy_sync.sincronizar_conteudo)",
  "base_analise": null,
  "rollback": "ref/backup_completo_20260722_230533.json",
  "principio": "CONTEUDO dev-vence; MAPA/MUNDO prod-vence; MEMORIA ausente.",
  "final_records": 5063,
  "sha256_arquivo": "d0225ceb10df8a39ca6e238b4aa4b9488a1339ad6fde791edf5a0ecd2bc3845a",
  "comparacao_baseline": null,
  "por_tabela": {
    "home.tbraca": {
      "modelo": "TbRaca",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 4,
      "contagem_esperada_pos_aplicacao": 4,
      "sha256_registros": "940c6bc6e37779016d55709dd746d54a1068415c8eb6a98dd8fd279193e7c617"
    },
    "home.tbessencia": {
      "modelo": "TbEssencia",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 4,
      "contagem_esperada_pos_aplicacao": 4,
      "sha256_registros": "ed40a75c53b0c204ac9f2aa911e259eb1a0b7d3d1b99e7d7a4a7e604255ef1e4"
    },
    "home.tbantecedente": {
      "modelo": "TbAntecedente",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 30,
      "contagem_esperada_pos_aplicacao": 30,
      "sha256_registros": "e2539b7a5a7c7ff551c89632a1f695d5a42077634da87246bccaaaba71ccf001"
    },
    "home.tbclasse": {
      "modelo": "TbClasse",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 13,
      "contagem_esperada_pos_aplicacao": 13,
      "sha256_registros": "1f1d660c0f3bc11cb5d83bdad6793f0f601173576f0de9d2071d2c87459c155d"
    },
    "home.tbopcaojogo": {
      "modelo": "TbOpcaojogo",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 281,
      "contagem_esperada_pos_aplicacao": 281,
      "sha256_registros": "d992f3efbad6cbad00b11a154aed0963d4cef7434724393ac07489b431315e73"
    },
    "home.tbmagia": {
      "modelo": "TbMagia",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 580,
      "contagem_esperada_pos_aplicacao": 580,
      "sha256_registros": "45af38eaf247db21b04a1ad40915390c33eb08b2556a0df39c86addfa234e88b"
    },
    "home.tbtalento": {
      "modelo": "TbTalento",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 139,
      "contagem_esperada_pos_aplicacao": 139,
      "sha256_registros": "6c2f2656cce7194df83b30c9e88ebe67ab80411dfb82bd2ac7eda74b40b48230"
    },
    "home.tbitemmagico": {
      "modelo": "TbItemMagico",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 955,
      "contagem_esperada_pos_aplicacao": 955,
      "sha256_registros": "0123580f388ec738c552a40f0e3582cfab8cbc67cd649af4145b6e8555dd351a"
    },
    "home.tblinhagem": {
      "modelo": "TbLinhagem",
      "acao": "upsert_por_slug",
      "linhas_no_arquivo": 16,
      "contagem_esperada_pos_aplicacao": 16,
      "sha256_registros": "5ebeb948769f3303284bc404b650fbe724d23803846611f62b1635afaa1e0eb0"
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
      "linhas_no_arquivo": 888,
      "contagem_esperada_pos_aplicacao": 888,
      "sha256_registros": "319fabeffebca4e6072ea83758ebb386462ae79c025c38123f7fe5bc6e44d431"
    },
    "home.tbrecursoclasse": {
      "modelo": "TbRecursoclasse",
      "acao": "substitui",
      "linhas_no_arquivo": 136,
      "contagem_esperada_pos_aplicacao": 136,
      "sha256_registros": "b11b7fa296a5e56ee9c950bf575e7d0d9535bc733144d4229c76e439b327fb9c"
    },
    "home.tbacessoopcao": {
      "modelo": "TbAcessoopcao",
      "acao": "substitui",
      "linhas_no_arquivo": 110,
      "contagem_esperada_pos_aplicacao": 110,
      "sha256_registros": "9f291c8c86a6af4939f0b894644d3e033a8b7b63daafbbf6bba30630d174b57d"
    },
    "home.tbtracoracial": {
      "modelo": "TbTracoracial",
      "acao": "substitui",
      "linhas_no_arquivo": 352,
      "contagem_esperada_pos_aplicacao": 352,
      "sha256_registros": "2959ae2daa4bb4abaaf460cd14b9e9dbd8763f20ce2dab6ad09dddb54dfe6b9b"
    },
    "home.tbcondicao": {
      "modelo": "TbCondicao",
      "acao": "substitui",
      "linhas_no_arquivo": 28,
      "contagem_esperada_pos_aplicacao": 28,
      "sha256_registros": "e65ef4e17e4f2103150844f03fdcadd42c0a93868d23f4d91bc616200b60ac04"
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
      "linhas_no_arquivo": 139,
      "contagem_esperada_pos_aplicacao": 139,
      "sha256_registros": "8fd967be8e3e30a8f8a83d811a22b4dab4eb1b2aeb9fdf0cdecd54be08dcb1d5"
    },
    "home.tbrecompensamestre": {
      "modelo": "TbRecompensaMestre",
      "acao": "substitui",
      "linhas_no_arquivo": 9,
      "contagem_esperada_pos_aplicacao": 9,
      "sha256_registros": "05a1fcc4f595265d473ae6cae2b5b9a29298f4a51795f28eb7c880433f300f0c"
    },
    "home.tbitemmundano": {
      "modelo": "TbItemMundano",
      "acao": "substitui",
      "linhas_no_arquivo": 302,
      "contagem_esperada_pos_aplicacao": 302,
      "sha256_registros": "2a223c0b2c862c57cb6d4921daff68f7c6366a842a9203c9ec662244c8e1bafb"
    },
    "home.tbbestiario": {
      "modelo": "TbBestiario",
      "acao": "substitui",
      "linhas_no_arquivo": 920,
      "contagem_esperada_pos_aplicacao": 920,
      "sha256_registros": "77faf24d2632195d12c19d0935ad538d11c0af4f746f2d6359903957a8d447da"
    },
    "home.tbarmadilha": {
      "modelo": "TbArmadilha",
      "acao": "substitui",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "0 no arquivo: modelo ausente no fixture e preservado na prod."
    },
    "home.tbmapdesenho": {
      "modelo": "TbMapDesenho",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 0,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/mapa da producao e preservado."
    },
    "home.tbmapmarker": {
      "modelo": "TbMapMarker",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 23,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/mapa da producao e preservado."
    },
    "home.tbregiao": {
      "modelo": "TbRegiao",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 23,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/mapa da producao e preservado."
    },
    "home.tbterritorio": {
      "modelo": "TbTerritorio",
      "acao": "skip_preserva_prod",
      "linhas_no_arquivo": 0,
      "contagem_esperada_pos_aplicacao": 9,
      "sha256_registros": null,
      "obs": "Fora do arquivo; mundo/mapa da producao e preservado."
    }
  },
  "validacao": {
    "deserialize_records": 5063,
    "merge_mem_ok": true,
    "merge_pass2_skipped": [
      "TbRegiao",
      "TbTerritorio",
      "TbMapMarker",
      "TbArmadilha",
      "TbMapDesenho"
    ],
    "memory_models_in_fixture": [],
    "line_endings": "CRLF",
    "bom": true
  }
}
