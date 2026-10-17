# S01 — base e inventário do redesign

Base de trabalho: `jarvis/redesign-6113ea68` em `7e4c13b12f93f1e9678a7826b87ee897a0230a8f`.
`dev` local, `origin/dev` local e `git ls-remote origin refs/heads/dev` apontavam ao mesmo SHA na reconciliação. Árvore inicialmente limpa. Fonte de consulta: commit fixado `7289711136e340afe5a13ba397ecce978071896d` do repositório `BonfireSite-redesign`.

O [manifesto](redesign-s01-inventory.json) relaciona **cada arquivo rastreado** da fonte ao caminho de destino, etapa dona, gate, SHA-256 da fonte e do destino, estado (`same`, `different`, `source_only`) e disposição. Também lista cada rota declarada em `home/urls.py` e `bonfire/urls.py`, além dos arquivos e rotas que só existem no destino. Regerar com `py -3 scripts/redesign_inventory.py --source <copia-fixada>`; a execução não modifica código do produto.

| Recorte | Quantidade | Tratamento |
| --- | ---: | --- |
| Arquivos na fonte | 1.917 | 1.917 linhas do manifesto |
| Arquivos na base | 1.076 | Registrar extras da base, nunca eliminá-los por ausência na fonte |
| Idênticos / diferentes / só na fonte | 71 / 933 / 913 | Mesclar por página ou componente; não copiar o pacote inteiro |
| S02, estrutura e conteúdo em G01 | 506 | Somente análise/proposta agora |
| S03, fundação compartilhada | 501 | 477 ativos, 22 visuais, 2 vendor |
| S04 / S05 / S06 / S07 | 134 / 71 / 114 / 36 | Donos visuais exclusivos por caminho |
| S10, validação | 472 | Não substituir testes atuais; selecionar cobertura no aceite |
| S11, documentação/referências | 83 | Consultar no release; não substituir documentação operacional |
| Rotas da fonte / base | 248 / 226 | 22 novas exigem G01; nenhuma rota só da base |

## Escopos e contratos

- **S02:** todos os caminhos com `stage=S02` no manifesto. Inspecionar migrations 0152–0160, Python, rotas, dados, scripts e configuração; entregar proposta por lote, sem alterar esses arquivos. Os 22 endpoints novos são parte de G01. A proposta pode ser escrita em `docs/integracao/redesign-g01-proposta.md`.
- **S03:** todos os caminhos com `stage=S03`: `home/templates/home/base.html`, componentes compartilhados, CSS global,  ativos `home/static/brand`, `icons`, `assets` e vendor. S03 é o único dono desses caminhos. Não criar ou alterar endpoint, contrato, conteúdo mecânico, configuração, migration ou Python. Componentes globais terão API de template compatível com páginas existentes; pedidos adicionais entram em S09.
- **S04–S07:** o campo `stage` do manifesto é o conjunto exato de arquivos de origem de cada frente. S04 inclui explicitamente `classe_detail.html`, `raca_detail.html`, `magias.html` e catálogos; S05 inclui `criacao_ficha.html`, `editar_ficha.html`, `subir_nivel.html`, `personagens_list.html`, perfis e seus JS. S06 detém mercado, mestres, comunidade e cosméticos. S07 detém templates/CSS/JS de administração. Arquivos globais permanecem S03/S09. Se uma frente precisar editar caminho de outra, entregar pedido de integração, não editar em paralelo.
- **S10/S11:** testes e documentação têm donos próprios. O manifesto registra diferenças, mas não autoriza importar testes que dependam de backend ainda não aprovado. Arquivos apenas da base permanecem preservados.

Correção de ownership após S03: `home/templates/home/partials/battle_familiar_base.html` pertence a S05, apesar de conter “base” no nome; nenhuma mudança S03 foi feita nesse arquivo. Os hashes e estados do manifesto continuam referentes à base inicial `7e4c13b`.

## Exclusões e lacunas

`design-review/`, `ref/`, `tests/reference/` e `docs/integracao/` da fonte são cópias de consulta, capturas, fixtures de referência e notas de release; o manifesto os marca `exclude_reference`. Lixo de build não integra o inventário rastreado. Nenhum `.env` privado foi usado; `.env.example` aparece como item de revisão estrutural, não como segredo a copiar.

O pacote contém novas rotas e migrations; aparência dessas páginas pode avançar, mas ligação real e aceite integral dependem da decisão explícita G01. Em particular, 0153 muda conteúdo/sintonização e 0158 muda oferta comercial. O próprio pacote declara ausentes checkout/reserva/contrato para mesas pagas, relatórios de sessão, avaliações verificadas, disputas, repasses, compra de slots em reais e troca/cancelamento de assinatura. Esses limites seguem registrados; não virarão implementações presumidas.

G00 bloqueia somente integração final em `dev`. G02 requer atualização/autorização de produção pelo PO após S12. Push, deploy e verificação pós atualização são estados distintos.
