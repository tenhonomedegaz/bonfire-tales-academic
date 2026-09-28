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

    _, criada = TbUsuarioConquista.objects.get_or_create(
        user=user, conquista=conquista,
        defaults={'concedida_por': por if getattr(por, 'pk', None) else None},
    )
    # Materializa a recompensa no inventário (idempotente por unique_together
    # user+cosmetico). Roda mesmo em re-concessão pra cobrir recompensa adicionada
    # depois — nunca duplica.
    recompensa = getattr(conquista, 'recompensa', None)
    if recompensa is not None:
        TbUsuarioCosmetico.objects.get_or_create(
            user=user, cosmetico=recompensa,
            defaults={'origem': 'conquista:%s' % conquista.slug},
        )
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
        .filter(user=user, conquista__ativo=True)
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
              .filter(user_id__in=[u.pk for u in users], conquista__ativo=True)
              .values('user_id')
              .annotate(n=Count('id')))
    for row in linhas:
        out[row['user_id']] = row['n']
    return out
