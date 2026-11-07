# -*- coding: utf-8 -*-
"""Limite de fichas por jogador + permissões da página de personagens.

Regra (pedida pelo usuário): cada jogador pode ter **1 ficha ativa**; +1 se
alcançou o rank Esmeralda (com pelo menos um personagem); +1 se for colaborador.
Staff/superuser não têm limite. O **cofre** (arquivado=True) NÃO conta no limite —
guardar uma ficha libera um slot ativo.

`is_rank_esmeralda` e `is_colaborador` são HOOKS com defaults seguros (hoje o rank
vive nas tabelas do bot Discord sem vínculo robusto com auth.User). Refinar depois
(ex.: campo `discord_user_id`/`is_colaborador` em UserProfile).
"""

LIMITE_BASE = 1

COLAB_TIER_RANK = {'conde': 1, 'marques': 2, 'duque': 3}


def colab_tier(user):
    """Highest active bot tier for a Bonfire account linked through Discord OAuth.

    Bot tables are read only and may be unavailable; absence of proven entitlement
    never creates a new grant. The catalog decides which item requires which tier.
    """
    if not getattr(user, 'is_authenticated', False):
        return None
    profile = getattr(user, 'profile', None)
    discord_id = str(getattr(profile, 'discord_user_id', '') or '').strip()
    if not discord_id:
        return None
    try:
        from django.db import transaction
        from django.utils import timezone
        from .models import BotMember, BotTransaction

        with transaction.atomic():
            member_email = BotMember.objects.filter(
                discordUserId=discord_id).values_list('email', flat=True).first()
            if not member_email:
                return None
            plans = BotTransaction.objects.filter(
                email__iexact=member_email.strip(), status=1,
                expirationDate__gt=timezone.now(),
                subscriptionPlan__startswith='colaborador-',
            ).values_list('subscriptionPlan', flat=True)
            tier = max((COLAB_TIER_RANK.get(str(plan).split('-')[1], 0)
                        for plan in plans), default=0)
            return next((name for name, rank in COLAB_TIER_RANK.items()
                         if rank == tier), None)
    except Exception:
        return None


def is_staff_user(user):
    return bool(getattr(user, 'is_authenticated', False) and (user.is_staff or user.is_superuser))


def is_rank_esmeralda(user):
    """Um slot pelo marco Esmeralda comprovado no site ou no bot."""
    if not getattr(user, 'is_authenticated', False):
        return False
    try:
        from django.db import transaction
        from .models import TbEventoConquista
        from .conquistas import direito_marco_ativo

        with transaction.atomic():
            markers = TbEventoConquista.objects.filter(
                conta=user, origem='site', tipo='rank_slot_13_granted',
                chave_origem=f'conta:{user.pk}:slot-esmeralda-nivel-13',
                payload_json__threshold=13,
            )
            for marker in markers:
                source_id = (marker.payload_json or {}).get('source_event_id')
                new_grant = TbEventoConquista.objects.filter(
                    conta=user, origem='site', tipo='character_milestone_granted',
                    payload_json__benefit='slot',
                    payload_json__source_event_id=source_id).first() if source_id else None
                if new_grant is None or new_grant.personagem_id is None or direito_marco_ativo(new_grant):
                    return True
    except Exception:
        pass
    try:
        from django.db import transaction
        from .models import BotMember, BotCharacterLog
        # As tabelas do bot são opcionais em dev/teste. O savepoint interno evita
        # que uma relação ausente invalide a transação externa do request/teste.
        with transaction.atomic():
            email = (getattr(user, 'email', '') or '').strip().lower()
            if not email:
                return False
            discord_ids = list(BotMember.objects.filter(
                email__iexact=email,
            ).values_list('discordUserId', flat=True))
            if not discord_ids:
                return False
            return BotCharacterLog.objects.filter(
                discordUserId__in=discord_ids,
                rankName__icontains='esmeralda',
            ).exists()
    except Exception:
        return False


def esmeralda_progress_needs_review(user, characters, *, has_right):
    """Indica progresso legado sem prova conciliada; nunca altera o limite."""
    if has_right or not getattr(user, 'is_authenticated', False):
        return False
    if any(character.nivel >= 13 for character in characters):
        return True
    try:
        from .models import TbEventoConquista
        return TbEventoConquista.objects.filter(
            conta=user, origem='site', tipo='character_level_up',
            payload_json__level_after__gte=13,
        ).exists()
    except Exception:
        return False


def is_colaborador(user):
    """+1 slot: assinatura COLABORADOR ativa (Asaas → tabela `transactions` do bot).
    Vínculo por e-mail (auth.User.email + e-mails do BotMember ligado por discord_user_id).
    Expira sozinho via `expirationDate` — a revogação no Discord o bot faz no ValidadeMembersJob.
    Default False em qualquer falha (ex.: tabela ausente no SQLite local)."""
    try:
        from django.db import transaction
        from django.db.models import Q
        from django.utils import timezone
        from .models import BotTransaction, BotMember
        with transaction.atomic():
            emails = set()
            if getattr(user, 'email', ''):
                emails.add(user.email.strip())
            perfil = getattr(user, 'profile', None) or getattr(user, 'userprofile', None)
            did = getattr(perfil, 'discord_user_id', None)
            if did:
                emails |= {e for e in BotMember.objects.filter(discordUserId=did)
                           .values_list('email', flat=True) if e}
            if not emails:
                return False
            cond = Q()
            for e in emails:
                cond |= Q(email__iexact=e)
            return BotTransaction.objects.filter(
                cond, subscriptionPlan__startswith='colaborador',
                status=1, expirationDate__gt=timezone.now()).exists()
    except Exception:
        return False


def is_mestre(user):
    """HOOK: quem pode criar/editar criaturas da COMUNIDADE. Staff sempre; rank
    Esmeralda (mestres/jogadores experientes) ou flag futura UserProfile.is_mestre."""
    if is_staff_user(user):
        return True
    if not getattr(user, 'is_authenticated', False):
        return False
    from .models import TbPerfilMestre
    participation = TbPerfilMestre.objects.filter(user=user).first()
    if participation and participation.status_mestre in ('suspenso', 'recusado'):
        return False
    if participation and participation.status_mestre == 'aprovado':
        return True
    perfil = getattr(user, 'profile', None) or getattr(user, 'userprofile', None)
    if getattr(perfil, 'is_mestre', False):
        return True
    return is_rank_esmeralda(user)


def slots_usados(user):
    """Personagens ATIVOS (fora do cofre)."""
    return user.personagens.filter(arquivado=False).count()


def is_mestre_ouro(user):
    """Proven lifetime purchase grants the extra character slot permanently."""
    if not getattr(user, 'is_authenticated', False):
        return False
    from .models import MestreOuroDireito
    return MestreOuroDireito.objects.filter(user_id=user.pk).exists()


def limite_detalhe(user):
    """Breakdown do limite, p/ o template explicar o cálculo ao jogador."""
    esmeralda = is_rank_esmeralda(user)
    from .models import TbEventoConquista
    from .conquistas import direito_marco_ativo
    grants = TbEventoConquista.objects.filter(
        conta=user, origem='site', tipo='character_milestone_granted',
        payload_json__level=13, payload_json__benefit='slot',
        personagem__isnull=False)
    slot_ficha = sum(
        1 for grant in grants
        if direito_marco_ativo(grant)
        and (grant.payload_json or {}).get('character_id') == grant.personagem_id
        and grant.chave_origem ==
        f'personagem:{grant.personagem_id}:nivel:13:direito:slot')
    colaborador = is_colaborador(user)
    mestre_ouro = is_mestre_ouro(user)
    # O primeiro slot de nível 13 coincide com o Esmeralda de conta; outras
    # fichas de nível 13 acrescentam direitos sem duplicar esse primeiro slot.
    slots_nivel = max(int(esmeralda), slot_ficha)
    total = LIMITE_BASE + slots_nivel + int(colaborador) + int(mestre_ouro)
    return {'base': LIMITE_BASE, 'esmeralda': esmeralda, 'colaborador': colaborador,
            'slots_ficha_13': slot_ficha, 'slots_nivel': slots_nivel,
            'mestre_ouro': mestre_ouro, 'total': total, 'ilimitado': is_staff_user(user)}


def get_character_limit(user):
    """Limite de fichas ATIVAS. None = ilimitado (staff/superuser)."""
    if is_staff_user(user):
        return None
    return limite_detalhe(user)['total']


def pode_criar(user):
    if is_staff_user(user):
        return True
    return slots_usados(user) < get_character_limit(user)


def pode_ver_ficha(user, personagem):
    """A ficha operacional só pertence ao dono ou à equipe."""
    return bool(personagem.dono_id == getattr(user, 'id', None)
                or is_staff_user(user))
