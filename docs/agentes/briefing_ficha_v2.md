# Briefing — Ficha v2 (fase de produto, definida pelo PO em 27/07/2026)

> Objetivo: transformar a ficha de "wiki bem organizada" em **ficha de mesa
> community-friendly**, com o Mercado como lugar de compra e o editar-ficha como
> ferramenta exclusiva da staff. Referências de disposição/estilo: a ficha D&D
> clássica (PDF do Scar) e o print da ficha atual anotado pelo PO — mantendo a
> identidade visual do site (Cinzel, paleta ember) e os TEMAS como diferencial.
> Anti-objetivo: "CSS genérico de IA".

Padrões operacionais: memória `verificacao-economica` (testes dirigidos na
iteração; suíte completa `--parallel 4` só no gate final; verificação-dupla só
em motor/migrações/deploy). Regras do projeto: descrição=verdade, snake_case,
ficha-de-log, zero if-por-tipo (registry).

## Ondas

### A — Quick wins (leve)
1. **Dinheiro sempre exibido em PO** (internamente pc continua): ficha, mochila,
   mercado, transações, level-up. PP/PC somem da exibição.
2. Remover o **botão de descanso do editar_ficha** (duplicado — o da ficha, sob
   os recursos, é o canônico).
3. **Magias fora do rodapé da aba 1** (já existe aba própria).
4. **Recursos compactos** e reposicionados ACIMA de "Características &
   Habilidades" (contadores pequenos, estilo a 3ª imagem do PO — não cartões
   gigantes).
5. Bloco **"Itens Sintonizados"** entre PV e Ataques — apenas informativo
   (equipamento vive na Mochila).
6. **Personalidade/Ideais/Vínculos/Defeitos** na ficha (modelo
   `TbPersonagemPersonalidade` já existe; dar UI de leitura + edição pelo dono).

### B — Aba Mochila (médio)
- Nova aba na ficha (par de Magias/Histórico): inventário completo + equipar/
  desequipar/sintonizar por **slot**, com visão de **slots livres × ocupados**
  (grade de slots: cabeça/torso/mãos/pés/anéis/acessórios/empunhadura/etc.,
  derivada dos slots reais do catálogo — sem hardcode de lista).
- `acessorio` não consome slot (regra do PO 27/07 — só concede efeito).
- Inventário e equipar SAEM do editar_ficha.
- Peso/valor total; consumíveis com qtd e botão de uso.

### C — Mercado marketplace (médio-grande)
- Compra E venda migram para as páginas do Mercado do site: o jogador escolhe o
  personagem ativo e compra/vende de lá (a ficha deixa de ter loja).
- Design de **loja de RPG** (vitrine, cards de mercadoria com preço em PO em
  destaque, categorias como prateleiras/lojas — Alquimia, Forja etc.), não
  lista-wiki. Reusar a identidade ember + tipografia do site.
- Guardas existentes intactos (sem-preço fora da venda; staff concede à parte).

### D — Aba "Magias & Opções" (médio)
- A aba de magias vira **Magias & Opções**: além das magias, lista TODAS as
  opções de classe do personagem (maestrias, estilos de luta, estilos de ki,
  segredos, manobras, metamagias...) — via registry/`pick:*`, ZERO hardcode.
- Permite TROCAR apenas as opções genuinamente trocáveis (swap:long_rest,
  swap:level_up etc. — a trocabilidade vem da tag, nunca de lista fixa).
- Conferir descrição completa de cada opção no lugar.

### E — Missões da staff (médio)
- **Modelo (decisão recomendada, PO pode vetar)**: estender o ledger
  `TbPersonagemAventura` (NÃO JSON no personagem): + `data_missao` (data da
  missão em si, não do lançamento), + `id_mestre` FK para o cadastro de mestres
  (cadastro já existe; passa a ser obrigatório — fim de string livre),
  + `detalhes_json` na LINHA (consumos: itens gastos, ouro gasto em RP,
  observações). 1 linha/missão = auditável, consultável, reversível; JSON só
  pro irregular. Volume real é pequeno (milhares de linhas, não milhões).
- **Edição de lançamentos** pela staff (corrigir lançamento errado): editar
  nome, data da missão, mestre, detalhes — com trilha de quem editou.
- Registrar consumos da missão: item consumível gasto (decrementa inventário)
  e ouro gasto em RP (debita carteira), pelo painel da staff.
- editar_ficha vira **ferramenta exclusiva da staff** (missões + conceder/
  reverter itens). Tudo que é do jogador migra pra ficha (ondas A-D).

### F — Identidade & modo mesa (grande)
- **Redistribuição dos blocos** guiada pelo PDF: coluna de atributos à
  esquerda; PV/CA/iniciativa/deslocamento no topo central; ataques centrais;
  recursos como contadores pequenos; características/habilidades à direita
  com melhor distribuição em fichas de nível alto (sem div rolável interna).
- **Modo mesa**: PV atuais + PV temporários editáveis na ficha, testes contra
  a morte (sucessos/falhas), inspiração — persistidos no personagem.
- **Notas do jogador** (campo livre).
- **Mobile**: layout de coluna única decente para consulta em sessão.
- **Versão imprimível** (print stylesheet ou export) no espírito do PDF.
- Temas continuam aplicando por cima (diferencial do site).

## Fora de escopo desta fase
Itens fungal (fonte da staff), Axe Beak (bestiário), rework Bestial/Folken,
VTT (toggles de combate seguem inertes).
