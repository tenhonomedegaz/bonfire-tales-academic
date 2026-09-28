# -*- coding: utf-8 -*-
"""Conquistas (F3) — concessão manual/staff + recompensa que cai no inventário +
vitrine no perfil.

Fonte única de concessão: `conceder_conquista(user, conquista, por=None)`. TODO
ponto que conceda uma conquista (admin action, futura automática) DEVE passar por
aqui — assim a recompensa sempre é materializada no inventário de cosméticos e a
operação é idempotente.

Vitrine: helpers que montam o estado das conquistas de um usuário pro perfil
público (compacto) e pro editor do próprio usuário. Secretas NUNCA aparecem pra
quem não as tem (não vaza existência). Batch pra /jogadores/ sem N+1.

Ver docs/agentes/arquitetura_personalizacao_perfil.md §3 e §7 (F3).
"""


def conceder_conquista(user, conquista, por=None):
    """Concede `conquista` a `user` (idempotente). Se ainda não tinha, cria a
    linha TbUsuarioConquista e, havendo recompensa, desbloqueia o cosmético no
    inventário (get_or_create em TbUsuarioCosmetico com origem 'conquista:<slug>').

    Retorna (criada: bool) — True se foi a primeira concessão, False se já tinha.
    Mesmo quando já tinha, garante que a recompensa esteja no inventário (auto-cura
    casos em que a recompensa foi ligada depois da concessão)."""
    if not user or not getattr(user, 'pk', None) or conquista is None:
        return False
    from .models import TbUsuarioConquista, TbUsuarioCosmetico

    concessao, criada = TbUsuarioConquista.objects.get_or_create(
        user=user, conquista=conquista,
        defaults={'concedida_por': por if getattr(por, 'pk', None) else None},
    )
    if concessao.revogada_em is not None:
        concessao.revogada_em = None
        concessao.save(update_fields=['revogada_em'])
        criada = True
    if getattr(por, 'pk', None) and concessao.concedida_por_id is None:
        concessao.concedida_por = por
        concessao.save(update_fields=['concedida_por'])
    # Materializa a recompensa no inventário (idempotente por unique_together
    # user+cosmetico). Roda mesmo em re-concessão pra cobrir recompensa adicionada
    # depois — nunca duplica.
    recompensa = getattr(conquista, 'recompensa', None)
    if recompensa is not None:
        posse, _ = TbUsuarioCosmetico.objects.get_or_create(
            user=user, cosmetico=recompensa,
            defaults={'origem': 'conquista:%s' % conquista.slug},
        )
        if posse.suspenso_em:
            posse.suspenso_em = None
            posse.origem = 'conquista:%s' % conquista.slug
            posse.save(update_fields=['suspenso_em', 'origem'])
    return criada


def conceder_conquista_em_massa(users, conquista, por=None):
    """Concede `conquista` a vários usuários. Retorna (concedidas, ja_tinham).
    Usa `conceder_conquista` por usuário (fonte única)."""
    concedidas = ja_tinham = 0
    for u in users:
        if conceder_conquista(u, conquista, por=por):
            concedidas += 1
        else:
            ja_tinham += 1
    return concedidas, ja_tinham


def registrar_criacao_personagem(personagem):
    """Registra a criação confirmada e concede a métrica da primeira ficha.

    Chamado somente pelo endpoint de criação real, dentro da mesma transação da
    ficha. Prévia e recriação de nível 1 usam o persistidor, mas não este serviço.
    """
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from .models import TbConquista, TbEventoConquista, TbPersonagem, TbUsuarioConquista

    regra = {
        'schema_version': 1, 'metric': 'characters_created',
        'scope': 'account', 'operator': 'gte', 'target': 1,
    }
    with transaction.atomic():
        # Duas criações simultâneas da mesma conta devem avaliar "primeira" em série.
        get_user_model().objects.select_for_update().only('pk').get(pk=personagem.dono_id)
        evento, _ = TbEventoConquista.objects.get_or_create(
            origem='site', chave_origem=f'personagem:{personagem.pk}:criado',
            defaults={
                'tipo': 'character_created', 'conta_id': personagem.dono_id,
                'personagem': personagem, 'agregado_id': personagem.pk,
                'ocorrido_em': personagem.criado_em,
            },
        )
        if evento.conta_id != personagem.dono_id or evento.agregado_id != personagem.pk:
            raise ValueError('Identidade do fato de criação inconsistente.')
        if TbPersonagem.objects.filter(dono_id=personagem.dono_id).exclude(pk=personagem.pk).exists():
            return evento
        for conquista in TbConquista.objects.filter(ativo=True, criterio='automatico',
                criterio_json__metric='characters_created').select_related('recompensa'):
            if conquista.criterio_json != regra:
                continue
            criada = conceder_conquista(personagem.dono, conquista)
            if criada:
                TbUsuarioConquista.objects.filter(user_id=personagem.dono_id, conquista=conquista).update(
                    evidencia_json={'evento_id': str(evento.pk), 'origem': evento.origem,
                                   'chave_origem': evento.chave_origem, 'agregado_id': personagem.pk},
                    definicao_json=regra,
                )
    return evento


def registrar_publicacao_cronica(cronica):
    """Registra a primeira publicação aprovada, sem contar revisões editoriais."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.db.models import Q
    from .models import TbConquista, TbCronica, TbEventoConquista, TbUsuarioConquista

    if cronica.status != 'aprovada' or not cronica.data_publicacao:
        raise ValueError('A crônica ainda não foi publicada.')
    regra = {
        'schema_version': 1, 'metric': 'stories_published',
        'scope': 'account', 'operator': 'gte', 'target': 1,
    }
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=cronica.autor_id)
        evento, _ = TbEventoConquista.objects.get_or_create(
            origem='site', chave_origem=f'cronica:{cronica.pk}:publicada',
            defaults={
                'tipo': 'story_published', 'conta_id': cronica.autor_id,
                'agregado_id': cronica.pk, 'ocorrido_em': cronica.data_publicacao,
            },
        )
        if evento.conta_id != cronica.autor_id or evento.agregado_id != cronica.pk:
            raise ValueError('Identidade do fato de publicação inconsistente.')
        anteriores = TbCronica.objects.filter(autor_id=cronica.autor_id).exclude(pk=cronica.pk)
        if anteriores.filter(Q(status__in=['aprovada', 'oculta']) |
                             Q(data_publicacao__isnull=False)).exists():
            return evento
        for conquista in TbConquista.objects.filter(
                ativo=True, criterio='automatico',
                criterio_json__metric='stories_published').select_related('recompensa'):
            if conquista.criterio_json != regra:
                continue
            if conceder_conquista(cronica.autor, conquista):
                TbUsuarioConquista.objects.filter(user_id=cronica.autor_id, conquista=conquista).update(
                    evidencia_json={'evento_id': str(evento.pk), 'origem': evento.origem,
                                   'chave_origem': evento.chave_origem, 'agregado_id': cronica.pk},
                    definicao_json=regra,
                )
    return evento


def registrar_fato_aventura(lancamento, *, estorno=False):
    """Persiste o fato do ledger do site, sem somá-lo a fatos ainda não vinculados do bot."""
    from .models import TbEventoConquista

    if estorno:
        if not lancamento.revertido or not lancamento.revertido_em:
            raise ValueError('O lançamento ainda não foi estornado.')
        tipo, sufixo, ocorrido = 'adventure_reverted', 'revertida', lancamento.revertido_em
    else:
        if lancamento.revertido or int(lancamento.qtd_aventuras or 0) <= 0:
            raise ValueError('O lançamento não está válido.')
        tipo, sufixo, ocorrido = 'adventure_recorded', 'registrada', lancamento.criado_em
    personagem = lancamento.id_personagem
    payload = {
        'ledger_id': lancamento.pk,
        'quantidade': int(lancamento.qtd_aventuras),
        'mestre_id': lancamento.id_mestre_id,
        'data_missao': lancamento.data_missao.isoformat() if lancamento.data_missao else None,
    }
    bot_quest_id = (lancamento.detalhes_json or {}).get('bot_quest_id')
    if bot_quest_id:
        payload['bot_quest_id'] = bot_quest_id
        bot_prova = (lancamento.detalhes_json or {}).get('bot_quest_proof')
        if bot_prova:
            payload['bot_quest_proof'] = bot_prova
    chave = f'aventura-ledger:{lancamento.pk}:{sufixo}'
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_ledger', chave_origem=chave,
        defaults={
            'tipo': tipo, 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': lancamento.pk,
            'ocorrido_em': ocorrido, 'payload_json': payload,
        },
    )
    if (evento.tipo != tipo or evento.conta_id != personagem.dono_id or
            evento.agregado_id != lancamento.pk or
            evento.payload_json.get('ledger_id') != lancamento.pk or
            evento.payload_json.get('quantidade') != payload['quantidade']):
        raise ValueError('Identidade do fato de aventura inconsistente.')
    return evento


def validar_vinculo_aventura_bot(personagem, bot_quest_id, quantidade):
    """Aceita apenas a identidade exata de uma missão finalizada do participante.

    Deve ser chamado sob lock da conta antes do crédito. Nome/data jamais servem de
    identidade; o vínculo fica no ledger do site e no fato canônico correspondente.
    """
    from django.utils import timezone
    from .models import BotQuest, TbPersonagemAventura, UserProfile

    quest_id = (bot_quest_id or '').strip()
    if not quest_id:
        return None
    perfil = UserProfile.objects.filter(user_id=personagem.dono_id).only('discord_user_id').first()
    discord_id = (perfil.discord_user_id or '') if perfil else ''
    if not discord_id:
        raise ValueError('Conta sem vínculo Discord verificado.')
    quest = BotQuest.objects.filter(pk=quest_id, status='finished').only(
        'id', 'questPlayers', 'rewardAventurasOverride', 'endDate').first()
    if quest is None:
        raise ValueError('Missão do bot inexistente ou não finalizada.')
    player = next((player for player in (quest.questPlayers or [])
                   if isinstance(player, dict) and str(player.get('userId')) == discord_id), None)
    if player is None:
        raise ValueError('Conta não consta entre os participantes confirmados da missão.')
    if player.get('removedAt'):
        if not player.get('removedWithReward') or int(player.get('rewardAmount') or 0) <= 0:
            raise ValueError('Participante removido sem recompensa verificável.')
        recompensa = int(player['rewardAmount'])
    else:
        recompensa = quest.rewardAventurasOverride
    # Sem valor explícito o bot não expõe neste contrato o crédito efetivo.
    if recompensa is not None and int(quantidade) != int(recompensa):
        raise ValueError('Quantidade diferente das aventuras concedidas pela missão do bot.')
    if TbPersonagemAventura.objects.filter(
            id_personagem__dono_id=personagem.dono_id, revertido=False,
            detalhes_json__bot_quest_id=quest_id).exists():
        raise ValueError('Esta missão do bot já foi vinculada a um lançamento ativo da conta.')
    return {
        'bot_quest_id': quest_id,
        'bot_quest_proof': {
            'discord_user_id': discord_id,
            'quest_end_at': quest.endDate.isoformat() if getattr(quest, 'endDate', None) else None,
            'removed_with_reward': bool(player.get('removedAt')),
            'reward_amount': int(recompensa) if recompensa is not None else None,
            'verified_at': timezone.now().isoformat(),
        },
    }


def registrar_fato_compra(transacao, *, historica=False):
    """Registra uma compra de item rastreável pelo ledger, nunca pela posse atual."""
    from .models import TbEventoConquista

    if (transacao.tipo not in {'compra', 'mercado-compra'} or
            (transacao.revertida and not (historica and transacao.revertida_em)) or
            int(transacao.valor_pc) >= 0):
        raise ValueError('Transação não é uma compra válida de item.')
    detalhes = transacao.detalhes_json or {}
    catalogo = detalhes.get('catalogo')
    if catalogo not in {'mundano', 'magico', 'oficina', 'comunidade'}:
        raise ValueError('Compra sem catálogo estruturado.')
    if (transacao.tipo == 'mercado-compra') != (catalogo == 'comunidade'):
        raise ValueError('Origem da compra inconsistente com o ledger.')
    try:
        catalogo_id = int(detalhes.get('catalogo_id') or 0)
        inventario_id = int(detalhes.get('inventario_id') or 0)
        quantidade = int(detalhes.get('qtd') or 0)
    except (TypeError, ValueError):
        raise ValueError('Compra sem identidade de item e quantidade.') from None
    if min(catalogo_id, inventario_id, quantidade) <= 0:
        raise ValueError('Compra sem identidade de item e quantidade.')
    payload = {
        'transacao_id': transacao.pk, 'catalogo': catalogo,
        'catalogo_id': catalogo_id, 'inventario_id': inventario_id,
        'quantidade': quantidade, 'valor_pc': int(transacao.valor_pc),
    }
    if catalogo == 'comunidade':
        anuncio_id = int(detalhes.get('anuncio_id') or 0)
        if anuncio_id <= 0:
            raise ValueError('Compra comunitária sem identidade do anúncio.')
        payload['anuncio_id'] = anuncio_id
    personagem = transacao.id_personagem
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_market', chave_origem=f'compra:{transacao.pk}:realizada',
        defaults={
            'tipo': 'item_purchased', 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': transacao.pk,
            'ocorrido_em': transacao.criado_em, 'payload_json': payload,
        },
    )
    if (evento.tipo != 'item_purchased' or evento.conta_id != personagem.dono_id or
            evento.agregado_id != transacao.pk or evento.payload_json != payload):
        raise ValueError('Identidade do fato de compra inconsistente.')
    if not historica:
        _avaliar_primeira_compra(personagem.dono)
    return evento


def registrar_fato_estorno_compra(compra, reembolso):
    """O estorno só existe após a reversão efetiva da compra e o crédito no ledger."""
    from .models import TbEventoConquista

    if (not compra.revertida or compra.revertida_em is None or
            reembolso.tipo != 'ajuste' or
            reembolso.id_personagem_id != compra.id_personagem_id or
            (reembolso.detalhes_json or {}).get('reverte_transacao') != compra.pk or
            int(reembolso.valor_pc) != -int(compra.valor_pc)):
        raise ValueError('Reembolso sem reversão financeira correspondente.')
    compra_fato = registrar_fato_compra(compra, historica=True)
    payload = {
        'transacao_id': compra.pk, 'reembolso_transacao_id': reembolso.pk,
        'compra_evento_id': str(compra_fato.pk),
        'quantidade': compra_fato.payload_json['quantidade'],
    }
    personagem = compra.id_personagem
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_market', chave_origem=f'compra:{compra.pk}:reembolsada',
        defaults={
            'tipo': 'item_purchase_refunded', 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': compra.pk,
            'ocorrido_em': compra.revertida_em, 'payload_json': payload,
        },
    )
    if (evento.tipo != 'item_purchase_refunded' or evento.conta_id != personagem.dono_id or
            evento.agregado_id != compra.pk or evento.payload_json != payload):
        raise ValueError('Identidade do fato de estorno inconsistente.')
    _avaliar_primeira_compra(personagem.dono)
    return evento


def _avaliar_primeira_compra(user):
    """Reavalia compras rastreáveis não estornadas sob bloqueio da conta.

    A concessão permanece como histórico quando perde suporte; a posse visual é
    suspensa apenas quando a própria conquista é sua origem registrada.
    """
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from .models import (TbConquista, TbEventoConquista, TbTransacao,
                         TbUsuarioConquista, TbUsuarioCosmetico)

    regra = {'schema_version': 1, 'metric': 'items_purchased',
             'scope': 'account', 'operator': 'gte', 'target': 1}
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        facts = TbEventoConquista.objects.filter(
            conta=user, origem='site_market', tipo='item_purchased').order_by('ocorrido_em', 'agregado_id')
        active_ids = set(TbTransacao.objects.filter(
            id_personagem__dono=user, revertida=False,
            pk__in=facts.values('agregado_id')).values_list('pk', flat=True))
        first = next((fact for fact in facts if fact.agregado_id in active_ids), None)
        rules = TbConquista.objects.filter(
            ativo=True, criterio='automatico', criterio_json__metric='items_purchased'
        ).select_related('recompensa')
        for rule in rules:
            if rule.criterio_json != regra:
                continue
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if first is not None:
                if grant is None or (grant.revogada_em and grant.concedida_por_id is None):
                    if conceder_conquista(user, rule):
                        TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                            evidencia_json={'evento_id': str(first.pk), 'origem': first.origem,
                                            'chave_origem': first.chave_origem,
                                            'agregado_id': first.agregado_id},
                            definicao_json=regra)
                elif (grant.concedida_por_id is None and
                      grant.evidencia_json.get('agregado_id') != first.agregado_id):
                    grant.evidencia_json = {
                        'evento_id': str(first.pk), 'origem': first.origem,
                        'chave_origem': first.chave_origem,
                        'agregado_id': first.agregado_id,
                    }
                    grant.save(update_fields=['evidencia_json'])
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                if rule.recompensa_id:
                    origin = 'conquista:%s' % rule.slug
                    other_grants = TbUsuarioConquista.objects.filter(
                        user=user, conquista__recompensa_id=rule.recompensa_id,
                        revogada_em__isnull=True).exclude(pk=grant.pk).exists()
                    if not other_grants:
                        TbUsuarioCosmetico.objects.filter(
                            user=user, cosmetico_id=rule.recompensa_id,
                            origem=origin, suspenso_em__isnull=True).update(suspenso_em=now)


def reprocessar_primeira_compra(user):
    """Recria fatos apenas de compras ativas com ledger estruturado comprovável."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from .models import TbEventoConquista, TbTransacao

    novas = invalidas = 0
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        purchases = TbTransacao.objects.filter(
            id_personagem__dono=user, revertida=False,
            tipo__in=['compra', 'mercado-compra'], valor_pc__lt=0,
        ).select_related('id_personagem').order_by('pk')
        for purchase in purchases:
            existed = TbEventoConquista.objects.filter(
                origem='site_market', chave_origem=f'compra:{purchase.pk}:realizada').exists()
            try:
                registrar_fato_compra(purchase, historica=True)
            except ValueError:
                invalidas += 1
                continue
            novas += int(not existed)
        _avaliar_primeira_compra(user)
    return {'novas': novas, 'invalidas': invalidas}


def progresso_aventuras_por_origem(user, discord_user_id=None):
    """Mostra fontes distintas; não soma saldos do bot com lançamentos do site."""
    from django.db import DatabaseError, transaction
    from .models import BotCharacterLog, TbPersonagem, TbPersonagemAventura

    personagens = list(TbPersonagem.objects.filter(dono=user).values_list(
        'pk', 'aventuras'))
    lancamentos = list(TbPersonagemAventura.objects.filter(
        id_personagem__dono=user, revertido=False, qtd_aventuras__gt=0
    ).values('id_personagem_id', 'qtd_aventuras', 'detalhes_json'))
    por_personagem = {}
    vinculadas_ao_bot = 0
    for row in lancamentos:
        quantidade = int(row['qtd_aventuras'])
        pk = row['id_personagem_id']
        por_personagem[pk] = por_personagem.get(pk, 0) + quantidade
        if (row['detalhes_json'] or {}).get('bot_quest_id'):
            vinculadas_ao_bot += quantidade
    site_total = sum(por_personagem.values())
    saldo_sem_ledger = sum(max(0, int(saldo or 0) - por_personagem.get(pk, 0))
                           for pk, saldo in personagens)
    divergencias = sum(int(saldo or 0) < por_personagem.get(pk, 0)
                      for pk, saldo in personagens)
    bot_logs, bot_disponivel = [], True
    if discord_user_id:
        try:
            # A tabela do bot é externa (managed=False) e pode não estar montada.
            with transaction.atomic():
                bot_logs = list(BotCharacterLog.objects.filter(
                    discordUserId=discord_user_id).order_by('id').values(
                        'id', 'characterName', 'adventuresPlayed'))
        except DatabaseError:
            bot_disponivel = False
    return {
        'site_total': site_total,
        'site_vinculadas_ao_bot': vinculadas_ao_bot,
        'saldo_sem_ledger': saldo_sem_ledger,
        'divergencias': divergencias,
        'bot_logs': bot_logs,
        'bot_disponivel': bot_disponivel,
        'discord_vinculado': bool(discord_user_id),
    }


# ─────────────────────────── Vitrine (perfil) ──────────────────────────────────
def _conquista_dict(conquista, obtida, concedida_em=None):
    """Dict uniforme pros templates de vitrine."""
    return {
        'slug': conquista.slug,
        'nome': conquista.nome,
        'descricao': conquista.descricao or '',
        # Ícone efetivo: arquivo enviado (icone_file) > icone_url. O template
        # continua com o fallback 🏆 quando vazio.
        'icone_url': conquista.icone_efetivo,
        'secreta': conquista.secreta,
        'obtida': obtida,
        'concedida_em': concedida_em,
    }


def _slugs_obtidas(user):
    """Mapa {conquista_id: concedida_em} das conquistas que o usuário TEM."""
    from .models import TbUsuarioConquista
    return dict(
        TbUsuarioConquista.objects
        .filter(user=user, conquista__ativo=True, revogada_em__isnull=True)
        .values_list('conquista_id', 'concedida_em')
    )


def conquistas_do_usuario(user, incluir_bloqueadas=True):
    """Estado das conquistas ATIVAS de `user` pra vitrine.

    Retorna dict:
        {
          'obtidas': [dict...],        # concedidas (com data), ordenadas por concessão desc
          'bloqueadas': [dict...],     # não-secretas não-obtidas (se incluir_bloqueadas)
          'total': int,                # Y do contador "X / Y" (ver regra abaixo)
          'obtidas_count': int,        # X do contador
        }

    Regra do contador Y: total de conquistas ATIVAS não-secretas + as SECRETAS que
    o user tem. Secretas NÃO-obtidas nunca contam nem aparecem (não vaza existência).
    """
    vazio = {'obtidas': [], 'bloqueadas': [], 'total': 0, 'obtidas_count': 0}
    if not user or not getattr(user, 'pk', None):
        return vazio
    from .models import TbConquista

    obtidas_map = _slugs_obtidas(user)  # {conquista_id: data}
    qs = (TbConquista.objects.filter(ativo=True)
          .order_by('ordem', 'nome'))

    obtidas, bloqueadas = [], []
    total_visivel = 0
    for c in qs:
        tem = c.id in obtidas_map
        if c.secreta and not tem:
            # Secreta não-obtida: invisível — não conta, não aparece.
            continue
        total_visivel += 1
        if tem:
            obtidas.append(_conquista_dict(c, True, obtidas_map[c.id]))
        elif incluir_bloqueadas:
            bloqueadas.append(_conquista_dict(c, False))

    # Obtidas mais recentes primeiro (X é o número delas).
    obtidas.sort(key=lambda d: d['concedida_em'] or 0, reverse=True)
    return {
        'obtidas': obtidas,
        'bloqueadas': bloqueadas,
        'total': total_visivel,
        'obtidas_count': len(obtidas),
    }


def conquistas_batch(users):
    """Pro /jogadores/ (opcional): {user_pk: obtidas_count} numa query. Evita N+1
    quando o card mostra o contador de conquistas."""
    users = list(users)
    out = {u.pk: 0 for u in users}
    if not users:
        return out
    from django.db.models import Count
    from .models import TbUsuarioConquista
    linhas = (TbUsuarioConquista.objects
              .filter(user_id__in=[u.pk for u in users], conquista__ativo=True,
                      revogada_em__isnull=True)
              .values('user_id')
              .annotate(n=Count('id')))
    for row in linhas:
        out[row['user_id']] = row['n']
    return out
