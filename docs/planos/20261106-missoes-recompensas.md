# Missoes: fontes, recompensas e integracao futura

## Regras confirmadas

- Missao e uma entidade; anuncio, relato, inicio, fim e resgate sao fontes/datas
  diferentes. Nao duplicar apenas porque titulo ou data divergem ligeiramente.
- Uma aventura concede 100 MM de base. Guardar separadamente quantidade-base,
  multiplicador, aventuras finais, MM-base, bonus de rank e MM final.
- Boost de mesa multiplica a base. O bonus de rank nao recebe esse multiplicador
  novamente e continua sujeito ao teto historico de recompensas dedicadas.
- Exemplo aprovado: 2 aventuras-base x2 = 4 finais; base 400 MM + bonus de 60 = 460 MM,
  nao 520. O teto de rank continua limitado a tres recompensas dedicadas.
- Fonte de relato e decisao administrativa prevalecem sobre duracao incompleta.
  Duracao ausente nao implica que a mesa nunca aconteceu.
- Somente legado privado validado, sem correspondente nativo, pode usar inferencia
  de centenas exatas. O total de uma mesa nativa pode conter bonus de rank:
  200 MM de A Casa que Nunca Dorme correspondem a 1 aventura, conforme relato.
- Nao inventar boost pelo dia da semana. Data do anuncio, inicio, fim ou resgate
  pode diferir do fim de semana do evento. Registrar confirmacao/fonte do boost.
- Teste tecnico e sem registro confirmado ficam excluidos das listagens/contagens,
  com evidencia auditavel. Nao apagar recibos, pagamentos ou provas financeiras.
- Confirmar quantidades/historico nao paga novamente moedas ja importadas.

## Contrato atual de dados

`TbRevisaoMissaoBot.evidence` recebe duas estruturas opcionais genericas, validadas
pela API de revisao existente; nenhuma regra por nome de mestre ou missao.

```json
{
  "reward_context": {
    "base_adventures": 2,
    "multiplier": 2,
    "reason": "weekend_double",
    "base_mm": 400,
    "dedicated_bonus_mm": 60,
    "final_mm": 460,
    "source": "discord_report_and_po_confirmation"
  },
  "mission_details": {
    "summary": "Resumo da sessao.",
    "participants": ["Nome publico do personagem"],
    "source_url": "https://discord.com/channels/SERVIDOR/CANAL/MENSAGEM"
  }
}
```

O link e ilustrativo; a API exige IDs numericos e o mesmo servidor da missao.
Resumo e nomes sao texto escapado na apresentacao. Nome historico nao comprova
propriedade de uma ficha e nao e suficiente para conceder recompensa automaticamente.
Clientes antigos nao devem apagar esses metadados ao revisar outro aspecto da missao.

`financial_mode=baseline` reconcilia com a planilha/credito ja existente, sem novo
pagamento. `new` continua restrito aos fluxos e recibos idempotentes anteriores;
nao e usado para a revisao do historico quitado desta entrega.

## Evidencias e operacao

- Foram lidos 557 registros de missao do servidor, com paginacao e revisao de fonte.
- O canal de relatos informado pelo PO foi consultado pelo bot, somente leitura;
  502 mensagens examinadas ate o inicio solicitado. Relatos relevantes ficam na
  evidencia privada, nao em prompts ou exportacoes indiscriminadas.
- Lote basico aplicado pela API: 15 missoes reconciliadas por relato, 11 testes
  tecnicos e tres entradas antes declaradas sem registro. Saldos MM/evento preservados.
- Dawn of a New Day foi vinculado ao registro The Dawn of a New Day. VIII tem
  1 aventura / 130 MM. X e XI: 4 / 460; Midnight: 4 / 400; Dawn: 4 / 550.
- Comparacao semantica da planilha online atual com a fonte importada: nenhum dos
  778 lancamentos antigos removido/editado; dois novos lancamentos de F76. Nao
  interpretar qualquer missao fora da planilha como teste ou autorizar credito duplicado.
- O lote de metadados/resumos e o filtro novo de exclusao exigem instalar o codigo
  desta entrega. Preparado em `%LOCALAPPDATA%/BonfireQA/mission-reconciliation-20261106/`.
  `basic-receipt.json` e prova da aplicacao basica, nao da instalacao do leitor novo.

## Proximas entregas da integracao com o bot

### Origem e realizacao, sem segunda fila de validacao

- No portfolio, `Manual · planilha` identifica a importacao historica. Um registro
  sintetico `legacy-import` na tabela do bot nao muda essa origem para sistemica.
- `Sistemica · bot` identifica uma missao nativa vinculada. Se tambem constar na
  planilha, exibir essa proveniencia adicional na mesma linha, sem duplicar a mesa.
- Filtro por origem preserva a escolha entre paginas. A origem e lida dos registros,
  nao de uma checkbox editavel pelo mestre ou de uma excecao por nome/usuario.
- A antiga fila "Verificar mesas realizadas" foi retirada. Seu endpoint retorna
  410 para quem tinha acesso; verificacoes antigas ficam somente para consulta.
- A elegibilidade comercial consulta o mesmo historico conciliado: sessoes concluidas
  nos ultimos 30 dias, usando a data de termino do bot quando registrada. Quatro
  aventuras em uma sessao contam como uma mesa, nao quatro. Testes excluidos,
  duplicatas e sessoes canceladas nao contam. Importacoes administrativas contam
  como historico manual, mas nao comprovam divulgacao aberta por si mesmas.
- Mesa aberta exige missao nativa publicada, com canal, nao classificada como
  Privada/private/particular. A autorizacao comercial continua separada; falha na
  consulta ao bot nao habilita a vitrine paga. Nenhum saldo e alterado na leitura.
- Nao ha formulario paralelo para remarcar a realizacao. Boost, vinculacao de fichas
  e jogadores automaticos pertencem ao fluxo da missao no bot, com recibos e
  privacidade; nao copiar IDs privados de `questPlayers` para o portfolio publico.
  A selecao/consumo de token de boost e a vinculacao automatica de participantes
  ainda dependem das entregas abaixo, nao foram implementadas por esta mudanca.

### Integracao pendente

1. Registro generico de campanha de boost: janela com fuso, multiplicador, criterios,
   fonte e estado. Eventos sao cadastrados; nao supor todo fim de semana em dobro.
2. Participacao com ficha e dono verificados, preservando nome historico, presenca,
   saida antecipada e recompensa individual. A exibicao publica respeita privacidade.
3. Token de boost seleciona a missao elegivel e explicita alcance. Boost pessoal de
   um jogador nao dobra automaticamente recompensas de todos nem MM do mestre.
4. Finalizacao registra recibo por missao/participante/versao e chama o motor atual
   de lancamento de aventuras. Retry nao duplica progressao, ouro ou moedas.
5. Boost posterior aplica apenas diferenca, com recibo compensatorio e verificacao
   de elegibilidade. Cancelamento/reversao preserva o historico, nao reescreve o passado.
6. Relato guarda resumo, fonte e participantes; assinatura/publicacao nao autoriza
   alterar automaticamente fichas por nomes colados no texto.
7. Central de Gestao oferece conciliacao com previa: comparar fontes, escolher
   registro canonico, marcar exclusao, conferir boost e ver impactos por jogador.

Esta lista e arquitetura posterior. Nao declara que tokens, campanhas ou creditos
automaticos ja foram integrados nesta rodada.
