# G01 — política de sincronização dos seis modelos do redesign

**Estado: proposta; implementação pendente de aprovação explícita do PO.**

O teste `home.test_deploy_sync.DeploySyncContractTests.test_all_managed_home_models_have_an_explicit_policy` encontrou seis modelos gerenciados sem classificação. A proposta é acrescentá-los a `MEMORY_MODELS` em `home/deploy_sync.py`, preservando os registros de cada ambiente e excluindo-os do importador de catálogo:

| Modelo | Motivo para preservar |
| --- | --- |
| `TbPerfilMestre` | Perfil e autorização vinculados ao usuário. |
| `TbMesaAnuncio` | Anúncio do mestre e revisão da staff. |
| `TbTrabalhoMestre` | Trabalho do mestre e revisão da staff. |
| `TbVerificacaoMesa` | Evidência de mesa concluída, vinculada à aventura e ao validador. |
| `TbAutorizacaoVitrine` | Decisão comercial da staff vinculada ao usuário. |
| `TbFeitoLenda` | Feito vinculado ao personagem, inclusive sua decisão de publicação. |

Este lote altera apenas a política de sincronização. Não cria migrations, não move linhas, não converte saldos e não autoriza publicação ou coleta de pagamentos. O teste de classificação deve passar, e testes de sincronização devem demonstrar que um fixture não sobrescreve nem apaga esses registros. G00 e G02 permanecem separados.

**Decisão solicitada:** aprovar ou adiar a inclusão desses seis modelos em `MEMORY_MODELS` como um único lote G01. Até a decisão, `home/deploy_sync.py` permanece inalterado.
