# Arquitetura — Personalização de Perfil e Ficha (híbrido Steam × Discord)

> Prioridade atual do PO. Este doc é a especificação pra implementação por agentes
> (Sonnet/Codex/Opus) com revisão humana. Base já existente (commit "perfis
> customizáveis"): NÃO recomeçar — **evoluir o que o Gaz construiu**.

## 1. Estado atual (fundação — já funciona)

| Peça | Onde | Nota |
|---|---|---|
| `UserProfile` (OneToOne User) | `models.py:783`, `TB_UserProfile` | `avatar_url`, `banner_url` (aceita GIF), `bio`, `profile_theme`, `avatar_frame`, `profile_effect` + economia (MM/evento) + discord |
| `TbPersonagem` aparência | `models.py:1072-1077` | `foto_url`, `token_url`, `banner_url`, `ficha_theme`, `foto_frame`, `ficha_effect` (migração 0045) |
| Opções hardcoded | `views.py:578-598` | `APPEARANCE_THEMES/FRAMES/EFFECTS` — dicts Python, whitelist fechada, tudo liberado pra todo mundo |
| Contexto compartilhado | `views.py:601-618` | `_appearance_choice()` + `_appearance_context()` — MESMO helper serve perfil e ficha |
| Tema via classe CSS | `perfil.css` | `.theme-*` só redefine CSS custom properties (`--profile-accent`...). 4 temas + default. Molduras/efeitos estáticos (sem keyframes) |
| Upload real | `views.py:621-658` | `_save_profile_upload` → `media/profile_uploads/user_<pk>/` (png/jpg/gif/webp, 8-12MB). **Só perfil; personagem ainda é URL manual** |
| Páginas | `/perfil/`, `/perfil/<username>/`, `/jogadores/` | jogadores_view já tem filtro "customizados" |

**O que NÃO existe:** catálogo em banco, inventário/desbloqueio por usuário, badges, títulos, conquistas, animação de moldura/efeito, upload pra personagem.

## 2. Princípios de design

1. **Catálogo no banco, render por classe CSS.** O cosmético é uma linha de tabela que aponta pra uma `css_class` (e opcionalmente um asset). Adicionar cosmético = INSERT + CSS, sem deploy de Python.
2. **Inventário separado de equipado.** O que o usuário TEM (inventário) ≠ o que está USANDO (campos string que já existem em `UserProfile`/`TbPersonagem` — não mudam de schema).
3. **Grátis por padrão, gate por origem.** GIF de banner/avatar é pra todos (decisão do PO). Molduras/efeitos/temas premium são gated por: conquista, MM, moeda de evento, braseiros (ficha), colaborador (dinheiro real), staff.
4. **Badges derivadas ≠ badges concedidas.** Staff/Colaborador/Mestre Ouro são *estado* (computadas na hora, nunca "dessincronizam"). Conquistas/eventos são *concessão* (linha no inventário).
5. **Perfil e ficha usam o MESMO sistema** (padrão já estabelecido pelo `_appearance_context`). Só muda a carteira de desbloqueio (usuário: MM/evento/dinheiro; personagem: braseiros).

## 3. Modelo de dados (novos modelos)

```python
class TbCosmetico(models.Model):            # db_table TB_Cosmetico — CATÁLOGO
    TIPO = [('tema','Tema'),('moldura','Moldura'),('efeito','Efeito'),
            ('titulo','Título'),('badge','Badge'),('banner_preset','Banner')]
    slug        = SlugField(unique=True)     # ex.: 'ember', 'gold-trim', 'campeao-torneio-2026'
    tipo        = CharField(choices=TIPO)
    nome        = CharField(100)             # "Brasas de Cinéria"
    descricao   = CharField(255, blank=True)
    raridade    = CharField(20, default='comum')      # comum|raro|epico|lendario (cor do card)
    css_class   = CharField(60, blank=True)  # 'theme-ember' / 'frame-gold-trim' (temas/molduras/efeitos)
    asset_url   = CharField(500, blank=True) # ícone de badge, overlay webp/gif de moldura animada
    animado     = BooleanField(default=False)
    # gate de aquisição (um dos):
    origem      = CharField(20, default='livre')
    # livre | conquista | loja_mm | loja_evento | loja_braseiro | colaborador | staff | evento_manual
    preco       = IntegerField(null=True)    # em MM/evento/braseiro conforme origem
    requer_plano= CharField(30, blank=True)  # p/ origem=colaborador: tier mínimo
    escopo      = CharField(10, default='ambos')  # perfil | ficha | ambos
    ativo       = BooleanField(default=True)
    ordem       = IntegerField(default=0)

class TbUsuarioCosmetico(models.Model):     # INVENTÁRIO (unique_together user+cosmetico)
    user         = FK(User, related_name='cosmeticos')
    cosmetico    = FK(TbCosmetico)
    desbloqueado_em = DateTimeField(auto_now_add=True)
    origem       = CharField(30)             # 'conquista:<slug>' | 'compra_mm' | 'staff' | 'seed'...

class TbConquista(models.Model):            # db_table TB_Conquista — definição
    slug, nome, descricao, icone_url
    secreta      = BooleanField(default=False)
    criterio     = CharField(20, default='manual')   # manual | automatico (fase 2)
    criterio_json= JSONField(default=dict)  # p/ automático: {"evento":"aventuras","gte":10}
    recompensa   = FK(TbCosmetico, null=True)        # desbloqueia cosmético ao conceder
    ordem, ativo

class TbUsuarioConquista(models.Model):     # unique_together user+conquista
    user, conquista
    concedida_em = DateTimeField(auto_now_add=True)
    concedida_por= FK(User, null=True)       # staff que concedeu (auditoria)
```

**Campos novos em modelos existentes (mínimos):**
- `UserProfile.titulo_equipado = CharField(60, blank=True)` — slug de cosmético tipo=titulo.
- `UserProfile.badges_destaque = JSONField(default=list)` — até N slugs escolhidos pelo usuário pra vitrine (estilo Steam "Destaque de conquistas").
- (ficha) `TbPersonagem.titulo_equipado` opcional — fase posterior.

**Badges derivadas (não vão pro inventário)** — helper `badges_derivadas(user)`:
`staff` (is_staff), `colaborador` (claim ativo via BotTransaction/`discord_user_id`), `mestre_ouro` (`UserProfile.mestre_ouro_ativo`), `fundador` (data de cadastro < X). Renderizadas junto das concedidas.

## 4. Fluxo de validação (troca mínima no código existente)

`_appearance_choice(value, choices, default)` evolui para:

```
_cosmetic_choice(user, tipo, value, escopo) ->
    cosmetico = catálogo[tipo][value] (ativo, escopo compatível)
    permitido = cosmetico.origem == 'livre'
                or inventário(user) contém
                or badge derivada cobre (staff etc.)
    return slug se permitido, senão default
```

- Os dicts `APPEARANCE_*` viram **seed** do catálogo (data migration) e morrem no Python; a view carrega o catálogo com cache (`django.core.cache`, TTL curto, invalida no admin-save).
- Página `/perfil/` (personalizar): grid atual (`.profile-appearance-grid`) passa a renderizar do catálogo com estado `livre | desbloqueado | bloqueado(origem/preço)` — bloqueado aparece com cadeado + como obter (igual Discord Nitro mostra o que você não tem).
- Compra: `origem=loja_mm` debita `UserProfile.moedas_mestragem` + `TbTransacaoMestre` (registro assinado — infra já existe); `loja_evento` idem em `moedas_evento`; `loja_braseiro` debita `TbPersonagem.braseiros` e o cosmético entra pro **usuário** com escopo=ficha; `colaborador` concede no claim (mesmo fluxo que dá tokens hoje).

## 5. Rendering (CSS/assets)

- **Temas**: manter o padrão atual (classe redefine variáveis). Tema novo = 4 variáveis. Suportar `--profile-accent` em degradê animado: adicionar keyframes genéricos uma vez (`@keyframes theme-shift`) e temas `animado=True` usam `background: linear-gradient(...); animation: theme-shift`.
- **Molduras animadas**: 2 mecanismos, por linha de catálogo:
  1. `css_class` com keyframes (glow pulsante, anel girando) — barato, resolve 80%;
  2. `asset_url` webp/apng overlay posicionado sobre o avatar (`.avatar-frame-overlay`) — pro estilo Discord de moldura ilustrada. `<img>` absoluto sobre o avatar, `pointer-events:none`.
- **Efeitos de perfil**: idem (classe p/ shaders CSS; asset p/ partículas gif/webp no header do perfil).
- **Badges**: `<img src=asset_url>` 24-32px com tooltip (nome+descrição+data). Linha de badges no card do jogador e no perfil público.
- **Títulos**: texto estilizado sob o username (cor por raridade).
- **Banner GIF**: já funciona (é URL). Adicionar `object-position` configurável depois (fase polish).

## 6. Telas

1. **/perfil/ (personalizar)** — abas: Aparência (temas/molduras/efeitos com estado de desbloqueio) · Badges & Títulos (escolher destaque + título) · Conquistas (progresso).
2. **/perfil/<user>/ (público)** — banner + avatar c/ moldura + título + linha de badges + vitrine de conquistas destacadas + personagens públicos. (Layout: evolução do atual.)
3. **/jogadores/** — cards já aplicam appearance individual; adicionar badges mini + título.
4. **Ficha** — seletor atual da ficha (ficha_detail 413-439) passa pelo mesmo catálogo/validação; upload real de foto/token do personagem (estender `_save_profile_upload` → `character_uploads/pers_<pk>/`, view nova no fluxo de edição).
5. **Admin** — CRUD de `TbCosmetico`/`TbConquista` + ação em massa "conceder conquista a usuários" (é assim que "conquistas de comunidade que nós cadastramos" operam no dia 1).

## 7. Fases de entrega (cada uma shippável)

| Fase | Entrega | Tamanho |
|---|---|---|
| **F0** | Correções da varredura (admin de item mundano quebrado + loja mundana sem mecânica — ver §8) | P |
| **F1** | Catálogo+inventário: modelos, migração, seed dos APPEARANCE_* atuais (todos `origem=livre`), validação por inventário, admin CRUD. Zero mudança visual | M |
| **F2** | Badges derivadas + concedidas + títulos no perfil/jogadores; `titulo_equipado`, `badges_destaque`; upload de foto/token do personagem | M |
| **F3** | Conquistas manuais: modelos, tela no perfil, ação admin de concessão em massa, recompensa→inventário | M |
| **F4** | Lojas (MM/evento/braseiro) + concessão via claim de colaborador; cadeados/preços na UI de personalizar | M |
| **F5** | Molduras/efeitos/temas ANIMADOS (keyframes + overlays), degradê custom do PO, polish (crop de banner, preview ao vivo) | M-G |
| — | Conquistas automáticas (criterio_json em signals: aventuras≥N, mesas mestradas≥N) | futuro |

**Notas de infra:** uploads seguem em `MEDIA_ROOT` local (whitenoise NÃO serve media — em prod conferir que waitress/cloudflared expõem `/media/`; se crescer, migrar pra R2/S3). GIFs pesados: manter limites atuais 8/12MB. `media/`, `backup_sqlite.json`, `conteudo.json` **devem entrar no .gitignore** (ver §8).

**Ads:** placeholders (`sidebar_support.html`/`horizontal_support.html` no base.html) — remover das páginas internas de jogador/mestre, manter só nas de consulta (spell/classe/raça), conforme PO. Gaz já está nisso.

## 8. Varredura — o que está quebrado/obsoleto (corrigir antes/junto da F1)

| # | Item | Severidade |
|---|---|---|
| 1 | `admin.py:2817-2838` — fieldsets de `TbItemMundanoAdmin` referenciam colunas removidas (dano/propriedades/maestria/ca/forca_minima/furtividade_desvantagem) → **admin de item mundano quebrado agora**. Fix: fieldsets só com `tags_json` + mecânica derivada readonly (`item_mecanica.mecanica_de_tags`) | **CRÍTICA** |
| 2 | `partials/itens_mundanos_content.html` (linhas 36-142) + `itens_mundanos_view` (views.py:7967) — template lê `item.dano/ca/propriedades/...` que não existem → seção mecânica **some silenciosamente** da loja pública. Fix: view anota cada item com `mecanica_de_tags()` (padrão já usado em `_criador_armas`) | **ALTA** |
| 3 | `taggear_itens.py` e `refinar_itens_mundanos_csv.py` — one-shot já cumpridos, crasham se re-executados (leem colunas mortas). Fix: deletar (ou mover p/ docs de histórico) | MÉDIA |
| 4 | `.gitignore` sem `media/`, `backup_sqlite.json`, `conteudo.json` (21MB de dumps + uploads de usuário passíveis de commit acidental) | MÉDIA |
| 5 | Assets soltos em `docs/agentes/` (Banner Gaz.png, Gaz Profile.gif, SKARNER*.png) — mover p/ media ou ignorar | BAIXA |
| 6 | CSS órfãos: `index.css`, `legado_collection_detail.css`, `legado_document_form.css` — deletar | BAIXA |
| ok | Fixtures, docs de tags, urls/views, templates: **sem problemas** | — |

**Fora de escopo por decisão:** evolução das tags_json (fica pra depois, com monitoramento humano).
