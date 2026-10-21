# G01 — política de sincronização dos seis modelos do redesign

**Estado: aprovado pelo PO em 21/10/2026, condicionado a não enviar perfis de teste para produção.** A aprovação cobre apenas a classificação dos seis modelos em `MEMORY_MODELS`; G02 continua necessário para atualizar produção.

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

**Decisão recebida:** inclusão aprovada com a condição acima. `dump_conteudo` e `export_restore_consolidado` exportam apenas `CONTENT_MODELS`; o teste de contrato verifica que o catálogo exclui `TbPerfilMestre` e que a sincronização ignora até um perfil de teste presente indevidamente no fixture. Antes de qualquer envio a produção, conferir o artefato efetivo e manter o gate G02.
