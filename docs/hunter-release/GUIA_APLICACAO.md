# Caçador: pacote único para alpha/QA

O arquivo privado `ref/backups/restore_unico_cacador_producao_20260928.json`
contém **107 adições** do rework, geradas a partir do backup de produção
`backup_completo_20260928_010338.json` (SHA-256
`a6a674829b8d46f01d8d3966b31bf0e7ca049cd3df597a23ab0b17d013222227`).
SHA-256 do pacote: `c637af3b3519259fcff8c06247a2b488338f77c552f822909ee4485dbeb83ae4`.
O backup original fica intacto e **não é o arquivo para upload**.

O código do destino precisa conter `home/hunter_restore_package.py` e o ramo
correspondente de `restore_backup` em `home/admin.py`. A árvore `dev` atual
chega a `home.0121`; aplicar antes as migrações pendentes do commit escolhido
(`python manage.py migrate --plan`, depois
`python manage.py migrate`); o JSON não cria tabelas. Confirmar host, banco e
schema do alpha, obter backup PostgreSQL recuperável e ensaiar o restore numa
cópia isolada desse alvo. O importador exige PostgreSQL, verifica o pacote
revisado, 29 personagens e seus vínculos originais, identidades de catálogo,
colisões de PK e de identidade natural. Só insere linhas ausentes, em transação;
repetir o mesmo arquivo insere zero. Se uma âncora ou identidade divergir,
**não forçar**: reconciliar os novos IDs e suas referências em outro pacote.

Após instalar o código e migrar o banco do alpha, no console
`/admin/server-logs/`, autenticar o console, escolher **Restaurar backup**,
enviar exclusivamente `restore_unico_cacador_producao_20260928.json`, digitar
`RESTAURAR` e conferir `Inseridos: 107; ja identicos: 0` (ou `0; 107` na
repetição). O guard que recusa fixtures genéricas só de catálogo permanece.
Não usar `Merge de conteúdo`, `sync_conteudo` ou o backup completo para esta
instalação. Se o servidor HTTP limitar uploads abaixo de 6,1 MB, ajustar esse
limite antes; a mensagem de sucesso do Django só existe após o POST chegar ao
aplicativo.

**Ativação explícita, ainda necessária após o upload:** definir no ambiente do
site `HUNTER_CREATOR_RULESET_CHECKSUM=da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289`
e reiniciar o processo do site. O upload sozinho não altera a configuração
carregada pelo processo. Sem esse valor, novas fichas e a prévia de
regularização não usam a revisão publicada. Verificar o criador, laboratório,
level-up e ficha nova após o restart.

As fichas antigas continuam vinculadas ao conteúdo antigo até cada jogador
abrir a comparação em `/personagem/<id>/regularizacao-cacador/` e confirmar
atributo, Ordem (a partir do nível 3), Segredos e cada escolha sem mapeamento.
O formulário registra as escolhas antigas afetadas na auditoria antes de
refazê-las; não converte por nome nem aplica regularização em massa. QA deve
verificar as quatro fichas legadas, inclusive a multiclasse, patrimônio,
moedas, magias, inventário, aventuras, histórico e rejeição de replay.

Ensaio já executado na cópia isolada do JSON de produção: 8.305 registros
carregados, 29 personagens, quatro Caçadores legados; o mesmo POST do admin
inseriu 107 linhas, repetição inseriu zero e colisão foi recusada. As 54
categorias de linhas preexistentes foram comparadas antes/depois. Regularização
explícita de uma ficha nível 1 e da multiclasse nível 20 passou nessa cópia.
Isso não comprova upload, migração, configuração ou smoke no alpha remoto.

Rollback seguro: remover o checksum do ambiente do site e reiniciar para
interromper novas criações na revisão. Manter as adições e revisões já usadas
por fichas; não apagar tabelas nem restaurar backup antigo sobre novas escritas.
Qualquer recuperação integral deve partir de dump PostgreSQL fresco e ser
ensaiada fora do alvo antes de uma troca coordenada.
