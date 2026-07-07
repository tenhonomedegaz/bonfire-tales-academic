# Levantamento de implementações & UI — Bonfire Tales (2026-06-23)

Legenda: ✅ feito · 🟡 parcial · ⬜ stub/falta

---

## 0. Recursos NOVOS pedidos (prioridade do PO)

### A. Mercado da Comunidade ⬜ (novo)
Jogador anuncia um **item mágico** que não vai mais usar e vende **pelo preço de venda do mercado**; como item mágico tem rotatividade, fica anunciado até alguém que precise pegar.
- **Modelo novo `TbAnuncioItemMagico`**: `vendedor` (TbPersonagem), `item_origem` (TbPersonagemItem), `id_item_magico` (TbItemMagico), `preco_pc` (= preço de **venda** do mercado, calculado, não editável), `status` (ativo/vendido/cancelado), `criado_em`, `comprador` (TbPersonagem null), `vendido_em`.
- **Fluxo**: anunciar → item sai do inventário do vendedor para *escrow* (anúncio); comprar → debita `carteira_pc` do comprador, credita o vendedor, move o `TbPersonagemItem` pro comprador (desequipado), marca anúncio `vendido`. Cancelar → devolve o item ao vendedor.
- **Preço de venda**: definir a regra (ex.: 50% do preço de compra do mercado) num helper `_preco_venda_pc(item)` reutilizado aqui e na venda normal.
- **Rotas**: `/mercado/comunidade/` (lista + filtros raridade/slot), POST `anunciar/`, POST `comprar-anuncio/<id>/`, POST `cancelar-anuncio/<id>/`.
- **UI**: página de mercado da comunidade (grid de anúncios com raridade/slot/sintonização + preço + botão comprar com seletor de personagem); seção “Meus anúncios” na edição da ficha (anunciar a partir do inventário + delistar). Aproveita a `/mercado/negociacoes/` (hoje stub) como casa natural.

### B. Login & vínculo com Discord ⬜ (novo)
Logar com Discord **ou** vincular a conta existente ao Discord.
- **Estado atual**: login custom por email/username (`EmailOrUsernameAuthenticationForm`), `UserProfile` (avatar_url, vlibras_enabled), tabelas `BotMember`/`BotCharacterLog` (read-only, vínculo hoje só por **email**) e permissões de rank já lendo `BotMember.email`. **Não há** lib de OAuth (django-allauth/social-auth).
- **Implementação**: OAuth2 do Discord. Opções: (1) `django-allauth` com provider `discord` (mais robusto, traz UI de social login); (2) fluxo OAuth2 **custom enxuto** (3 endpoints, sem dependência grande) — combina melhor com o estilo atual do projeto.
- **Modelo**: adicionar `discord_user_id` + `discord_username` ao `UserProfile` (ou `DiscordLink` 1-1). O `discord_user_id` vira o vínculo **forte** com `BotMember` (hoje frágil, só email).
- **Rotas**: `/discord/login/` (inicia OAuth), `/discord/callback/` (cria/vincula conta), POST `/perfil/discord/desvincular/`.
- **Settings**: `DISCORD_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI`.
- **UI**: botão “Entrar com Discord” na tela de login; seção “Contas vinculadas / Conectar Discord” no perfil (mostra discord_username + data + desvincular); toast no cadastro se o email já existe no bot (“conecte sua conta para puxar seus personagens”).

---

## 1. Stubs prontos pra virar página (quick wins) ⬜
Rotas que hoje caem em `placeholder_view` (página vazia). Muitas só precisam de uma view + reaproveitar template de catálogo existente (`catalogo.html`).
| Rota | Vira | Esforço |
|---|---|---|
| `/jogador/idiomas/` | Catálogo de **Idiomas** (`TbIdioma` já existe e populado: categoria basal/derivado/exótico, nome_mundo, transcrição) | baixo (reusa catálogo) |
| `/magias/escolas/` | Catálogo de **Escolas de Magia** (agrupa `TbMagia` por `escola`) | baixo |
| `/magias/congregacao/` | Congregação Mágica (ordens/lideranças mágicas — modelo novo ou conteúdo) | médio |
| `/atualizacoes/` | **Notas de Atualização** (changelog — reusa `TbJornal` filtrado ou estático) | baixo |
| `/mundo/cosmo/` | Cosmologia (conteúdo estático ou `TbCosmologia`) | médio |
| `/mundo/linha-do-tempo/` | Timeline (modelo novo `TbEventoMundo` + timeline visual) | médio |
| `/mundo/faccoes/` | Facções (modelo novo ou reuso de Organizações) | médio |
| `/mestre/armadilhas-e-perigos/` | **Armadilhas** (`TbArmadilha` novo: tipo, ND, save, dano) | médio |
| `/mestre/tipos-de-missoes/` | Tipos de missão (catálogo) | baixo |
| `/mestre/missoes/` | Conduzindo missões (canvas estruturado p/ mestre) | médio |
| `/mestre/mercado-de-mestre/` | Mercado de mestre (loot por ND/raridade, gerador) | médio |
| `/mercado/negociacoes/` | **Mercado da Comunidade** (recurso A acima) | alto |
| `/colaborador/`, `/catarse/`, `/quem-somos/` | Páginas institucionais (conteúdo estático) | baixo |

---

## 2. Criador / Ficha de Personagem
**✅ Feito:** criação (point-buy + raça/linhagem/essência + classe nv1 + antecedente), level-up (subir nível, subclasse, ASI, aprender/trocar magia), equipar (1 armadura + 1 escudo), mercado mundano embutido na edição, carteira, listagem/arquivar/excluir, ficha read-only com `derive()`.

**🟡 Parcial / ⬜ Falta — maiores oportunidades de UI+mecânica:**
- **Efeitos de item mágico equipado/sintonizado** — `TbPersonagemItem.sintonizado` existe, mas o `derive()` **não aplica** bônus passivos das tags do item. → gerenciador de **Sintonização (0/3)** + `apply_tags` para itens. (liga direto no Mercado da Comunidade)
- **Compra de item mágico** — `personagem_comprar_item` só aceita `TbItemMundano`; falta aba de itens mágicos (filtro raridade/slot/sintonização).
- **Magias preparadas dinâmicas** — `TbPersonagemMagia.preparada` existe sem UI (Clérigo/Druida). → painel de preparação por círculo.
- **Recursos de classe** (Fúria/Ki/Inspiração) — `TbPersonagemRecurso` sem UI de usar/recuperar (descanso curto/longo).
- **Multiclasse** — modelo (`TbPersonagemClasse`, N classes) pronto, sem UI/recalculo. → seção “Adicionar classe”.
- **Escolhas de classe em níveis altos** — metamagia, aspecto-selvagem, invocações místicas, forma selvagem (com statblock do `TbBestiario`): sem seletores dinâmicos.
- **Condições aplicadas na ficha** (Envenenado, Assustado…) com checagem de imunidades.
- **Exportar JSON/PDF** — sem `to_json()`/endpoint (a task #8 pendente). → `/api/personagem/<pk>/export`.
- **Componentização** dos templates gigantes (`criacao_ficha.html`, `editar_ficha.html`) em partials.
- Extras: validador de regras inline, biblioteca de builds públicas, popup de detalhe de ataque (fórmula d20+prof+mod), dark mode da ficha.

---

## 3. Mercado & Economia
**✅** mundano (compra, carteira, `_preco_em_pc`/`_pc_display`). **⬜** venda (remover item, receber PC), preço de venda ≠ compra, itens mágicos no mercado, sintonização, **Mercado da Comunidade** (recurso A), Mercado de Mestre (loot por ND), histórico de transações.

---

## 4. Ferramentas de Mestre
**✅** Bestiário (`/mestre/bestiario`, `TbBestiario`), Condições (`/mestre/condicoes`, `TbCondicao`). **🟡** ambos só editáveis via admin Django (sem form no site). **⬜** Armadilhas, Mercado de Mestre, Tipos de Missão, Conduzindo Missões (todos stub, sem modelo).
**UI:** statblock 5e visual no bestiário (grid de atributos, CA/PV, badges de ND coloridos, filtros por ND/tamanho/tipo), botão “imprimir statblock”, accordion de efeitos nas condições, forms inline staff p/ criar criatura/armadilha sem admin.

---

## 5. Mundo / Lore
**✅** Regiões/mapa (`TbRegiao`/`TbTerritorio`/`TbMapMarker`), Organizações, Jornal (`TbJornal`), Crônicas (`TbCronica`), wiki de edição (`wiki_update_*` p/ região/território/marcador). **🟡** stats de região/território (13/8 campos) sem form de edição; lore markdown só via POST. **⬜** Cosmologia, Linha do Tempo, Facções (stubs).
**UI:** modal de edição de região/território (lore markdown com preview live, color picker, stats em radar/bar chart), timeline de crônicas, editor visual de organizações, busca global de mundo, filtro por camada (superfície/subterrâneo).

---

## 6. Magias & Catálogos
**✅** Magias (`/magias/listas`), Talentos (`/jogador/talentos`), Antecedentes, Classes/Raças (catálogos ricos com `catalogo.html`/`talentos.html`), motor de tags (`tag_engine` + `validate_tags`). **🟡** filtro de escola embutido falta; antecedentes não renderizam “Reino/Deus”. **⬜** Escolas de Magia, Congregação, Idiomas (stubs), wiki-edit p/ magia/talento/idioma.
**UI:** checkbox de Escola no filtro, modal “leia mais” em magias, filtro avançado (escola+nível+concentração+ritual), notas de atualização.

---

## 7. Conta & Discord
**✅** login email/username, cadastro, perfil (avatar, troca de senha, VLibras), `UserProfile` + signal, permissões de rank via `BotMember.email`. **🟡** vínculo bot só por email (frágil), perfil sem seção Discord. **⬜** **Login/vínculo Discord** (recurso B), flag `is_colaborador`, sincronização robusta user↔BotMember por `discord_user_id`.

---

## 8. Transversal / infra
- **Dual-backend** (PostgreSQL em prod, SQLite local) com fallback — consolidar/observar inconsistências.
- **Componentização** de templates longos; **dark mode** nativo; **busca global**; **exportações** (PDF/PNG/JSON de fichas, statblocks, cards de região).
- **Forms no site** para staff (hoje muita coisa só via admin Django).

---

## Sugestão de ordem
1. **Quick wins de stub** (Idiomas, Escolas de Magia, Notas de Atualização) — baratos, dão volume de conteúdo.
2. **Discord (recurso B)** — desbloqueia identidade/rank/sincronização com o bot.
3. **Itens mágicos na ficha** (compra + sintonização + `apply_tags`) — pré-requisito do Mercado da Comunidade.
4. **Mercado da Comunidade (recurso A)** — depende do item mágico estar “vivo” na ficha.
5. **Recursos de classe + preparadas + multiclasse** — completam o ciclo da ficha.
6. **Ferramentas de Mestre + Mundo** (statblock visual, timeline, armadilhas).
