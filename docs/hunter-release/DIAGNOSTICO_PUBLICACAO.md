# Diagnostico da publicacao do Cacador no alpha

O restore do pacote nao ativa o ruleset. No processo que serve o site, configure
`HUNTER_CREATOR_RULESET_CHECKSUM=da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289`
e reinicie esse processo. Confirme que o processo le a configuracao efetiva;
alterar um arquivo `.env` que seja sobreposto por variavel de ambiente nao basta.

Com o codigo deste diagnostico instalado, entre como superusuario, desbloqueie
`/admin/server-logs/` com a senha do console e abra
`/admin/server-logs/hunter-publication-status/`. `code=ok`, `published=true`,
`orders=8` e `levels=20` confirmam apenas a integridade do catalogo publicado
no processo consultado. `config_missing` indica checksum ausente no processo;
`ruleset_missing` indica que o checksum configurado nao existe no banco
acessado; os outros codigos identificam a etapa do catalogo que falhou.
Nao repita o restore para corrigir configuracao. O endpoint nao permite SQL nem
escrita e nao fornece dados de jogadores.

Depois, abra `/jogador/classes/cacador/` e confira d6 no nivel 1, progressao
1-20 e oito Ordens sem legadas. Valide separadamente criador, laboratorio,
level-up, ficha nova e fichas antigas. O diagnostico local contra o backup de
29/09/2026 respondeu 200 com o checksum final e 503 com checksum vazio; isso
nao confirma a configuracao nem o QA do alpha remoto.

## Apresentacao dos cards

A correcao visual usa `home/rules/hunter_display.json` junto ao codigo da pagina.
Publique ambos na mesma atualizacao do site e reinicie o processo web. Nao e
necessario repetir o restore, migrar o banco ou trocar
`HUNTER_CREATOR_RULESET_CHECKSUM`: a revisao publicada e as fichas permanecem
inalteradas. Na pagina, confira paragrafos, subtitulos e listas dos cards,
os cinco cards explicativos de Ordem/Habilidade da Ordem, o marcador de
atributo na tabela e cada link das oito Ordens. Repita a verificacao em desktop
e em largura movel; o diagnostico `code=ok` nao valida esses aspectos visuais.
