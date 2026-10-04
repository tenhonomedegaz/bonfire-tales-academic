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


def is_staff_user(user):
    return bool(getattr(user, 'is_authenticated', False) and (user.is_staff or user.is_superuser))


def is_rank_esmeralda(user):
    """HOOK: True se o jogador tem algum personagem no rank Esmeralda.
    Tenta via e-mail (auth.User.email → bot Discord); default False em qualquer falha."""
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
    colaborador = is_colaborador(user)
    mestre_ouro = is_mestre_ouro(user)
    total = LIMITE_BASE + (1 if esmeralda else 0) + (1 if colaborador else 0) + (1 if mestre_ouro else 0)
    return {'base': LIMITE_BASE, 'esmeralda': esmeralda, 'colaborador': colaborador,
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
    """Dono, staff, ou ficha pública."""
    return bool(personagem.dono_id == getattr(user, 'id', None)
                or is_staff_user(user) or personagem.publico)
