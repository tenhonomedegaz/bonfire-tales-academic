# Integração compartilhada S09

- `home/static/css/components/editorial-ad.css` está presente, mas o componente
  `home/templates/home/components/horizontal_support.html` ainda depende da
  inclusão global da folha em `home/templates/home/base.html`. Validar os slots
  de publicidade nas larguras móvel e desktop, preservando os IDs e scripts
  atuais de anúncios.
- A consulta nova do mercado usa `dual_distance` em
  `market_consultation_cards.html` e `market_item_notes.html`. A biblioteca e
  suas dependências Python estão no lote G01-A da proposta; integrar as telas
  somente após aprovação e compilação dos dois templates.
- A validação responsiva e funcional conjunta deve cobrir navegação por
  teclado, foco visível, formulários do admin, mercado e charbuilder, além dos
  fluxos legados de pagamento e publicidade.
