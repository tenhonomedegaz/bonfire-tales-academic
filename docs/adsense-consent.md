# AdSense: publicacao e consentimento

## Codigo

- ADSENSE_PUBLISHER_ID continua ca-pub- seguido de 16 digitos para meta e script.
- /ads.txt publica pub- seguido dos mesmos digitos, sem ca-. Configuracao invalida
  retorna 404, sem publicar uma declaracao incorreta.
- A tag oficial so carrega nas paginas editoriais que habilitam anuncios.
- A CMP certificada do Google e distribuida pela propria tag do AdSense apos
  publicar uma mensagem no painel. Nao ha uma CMP caseira nem aceite presumido.
- O rodape oferece Privacidade e cookies quando a CMP informa gdprApplies=true
  e sua API esta pronta. O clique reabre a mensagem oficial para rever escolhas.
- Fora da regiao, API ausente ou erro: o controle permanece oculto. O site nao
  modifica strings TCF nem grava consentimento em cookies/localStorage proprios.
- Nao adicionamos Analytics nem configuracoes que concedem consentimento.

## Acao no painel (necessaria)

1. Entrar na conta titular em https://adsense.google.com/ .
2. Abrir Privacidade e mensagens > Regulamentacoes europeias > Criar/Gerenciar.
3. Selecionar bonfiretales.com.br. Usar a politica existente:
   https://bonfiretales.com.br/privacidade/ .
4. Usar portugues como idioma padrao; adicionar outros idiomas apenas se forem
   revisados. Exibir Consentir, Nao consentir e Gerenciar opcoes na primeira tela.
   Nao bloquear acesso ao conteudo por recusa de publicidade personalizada.
5. Selecionar EEE, Reino Unido e Suica, conferir os fornecedores declarados e
   publicar a mensagem. Nao marcar empresas que o site nao utiliza por suposicao.
6. Depois do /site-update, conferir a publicacao de /ads.txt e pedir nova leitura
   no AdSense, em Sites > bonfiretales.com.br > ads.txt > Verificar atualizacoes.

Publicar codigo nao publica a mensagem no painel. Sem sessao autenticada do
titular, esta etapa permanece pendente; nao declarar consentimento ativo.
Nao e necessario trocar chave da API Bonfire nem alterar o banco do site.

## Conferencia

- /ads.txt: google.com, pub-[discord-id], DIRECT, f08c47fec0942fa0 .
- Meta/script: manter ca-pub-[discord-id].
- Sem bloqueador, testar a home com ?fc=alwaysshow&fctype=gdpr conforme a API
  oficial. Essa e uma previa de desenvolvimento, nao um teste de geolocalizacao.
- Aceitar/recusar/gerenciar e rever a escolha no rodape usando a mensagem real.
- Conferir outra vez em acesso da regiao abrangida. A simulacao local de eventos
  testa somente a integracao, nao certifica a publicacao nem a conformidade legal.

## Referencias oficiais

- https://support.google.com/adsense/answer/9785052
- https://support.google.com/adsense/answer/10960768?hl=pt-BR
- https://support.google.com/adsense/answer/13554116
- https://developers.google.com/funding-choices/fc-api-docs
