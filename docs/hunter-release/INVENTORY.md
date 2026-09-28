# Inventário do Caçador

Escopo: referência HTML local completa e baseline do repositório. Não representa
o conteúdo do banco de produção. O preflight de produção pertence ao aceite de
banco e deve comparar os registros reais antes de qualquer publicação.

`inventory.json` registra o hash da fonte, todas as 211 seções, progressão 1–20,
oito Ordens, payloads e hashes dos registros antigos associados, os 53 registros
de habilidades e as referências dos quatro documentos de regras. Cada seção
nova tem uma ação explícita; cada habilidade antiga conserva seu ID e payload.
Correspondências por nome, nível e Ordem são candidatos para revisão, nunca
equivalência automática de escolhas ou autorização de migração.

| Conteúdo | Baseline | Referência / ação |
|---|---|---|
| Ordens | Aliança Selvagem, Mutantes, Viajantes, Enxame, Sombras, Exterminadores de Monstros | Aliança Selvagem, Crepúsculo, Despertar, Enxame, Exorcistas, Exterminadores, Mutantes, Viajantes Primordiais; preservar as seis antigas, cadastrar oito novas; não inferir renomeações |
| Preparos de Caçada | nível 1 | nível 2; nova revisão e nova seleção de Estilo de Luta |
| Instinto de Caçador | nível 2 | nível 3; respeitar a revisão da ficha |
| Dado de Caçador | d4/d6/d8/d10/d12 nos níveis 1/3/7/11/15 | d6/d8/d10/d12 nos níveis 1/5/11/17 |
| Inimigos favoritos | aumentos em 2/6/14 | aumentos em 2/8/14 |
| Pontos de Segredo | 4/6/8/10/12/14/16 nos níveis 2/4/7/10/13/16/19 | nível de Caçador a partir do nível 2 |
| Segredos | quantidade conhecida por progressão | Linha Mestra e preparo das outras Linhas limitado pela proficiência; escolhas antigas exigem regularização explícita |
| Conjuração | um registro na fixture atual | INT/SAB escolhível, catálogo e progressão da nova revisão; a anotação histórica de duplicidade não prova duplicidade atual |

As descrições completas por nível e Ordem estão em
`home/rules/hunter_content.json`, derivadas da mesma fonte e exibidas no
laboratório. Incluem subtítulos de regras e tabelas convertidas em texto. Os
30 Segredos, suas três Linhas e graus permanecem no catálogo
`home/rules/hunter_rework.json`. Texto disponível não significa efeito automatizado.

Dependências de implementação identificadas: Marca persistente, seleção INT/SAB
propagada à conjuração, efeitos das habilidades e Ordens, companheiros,
integração criador/level-up/ficha e regularização assistida. O inventário mantém
os efeitos antigos e novos para implementar esses contratos sem sobrescrever
fichas antigas. Referências de magias são associações por lista ou nome no
artigo; não substituem validação de IDs no catálogo executável.

Classificação do pacote: os leitores versionados, preparo/uso/descanso de
Segredos e recibos existentes são dependências do marco e possuem evidência
regional, mas ainda precisam do aceite integrado. As correções existentes de
criador, recursos, magias e clérigo exigem revisão do manifesto antes do commit.
O protótipo VTT permanece fora deste marco. Nenhum arquivo local deve ser
descartado ou incluído automaticamente no commit.

Para reproduzir, executar `prepare_ranger_rework --inventory` com `--source`
apontando ao HTML local, `--baseline home/fixtures/conteudo.json`, `--output`
e `--content-output` apontando a arquivos novos. O comando recusa sobrescrita.
Validação regional: `manage.py test home.test_hunter_inventory
home.test_ranger_reference home.test_hunter_rework --keepdb --noinput`.
