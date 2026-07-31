# -*- coding: utf-8 -*-
"""Social do perfil — CURTIR e SEGUIR.

Camada fina sobre TbPerfilCurtida/TbPerfilSeguidor com DUAS responsabilidades:

1. **Estado de um perfil** (`estado_social`) — as contagens do perfil visitado +
   se o visitante já curtiu/segue. Formato único, usado pelo perfil público, pela
   prévia do editor e pela resposta JSON dos endpoints de toggle: o que o
   template lê depois de um fetch é exatamente o que ele leu no render inicial.
2. **Batch** (`social_counts_batch`) — contagens de VÁRIOS usuários em 2 queries
   (uma por tabela, `values().annotate(Count)`), no mesmo espírito de
   `badges.perfil_badges_batch`. É o que mantém /jogadores/ sem N+1.

Toggle é idempotente por construção: `get_or_create` cria ou a linha já existe
(unique_together no banco cobre corrida), e o caminho de desfazer é um `delete()`.
Curtir/seguir a si mesmo é recusado na view (400) — aqui `pode_interagir` diz por quê.
"""
from django.db.models import Count


def _pk(user):
    return getattr(user, 'pk', None) if user is not None else None


def contagens(user):
    """{curtidas, seguidores, seguindo} do usuário. 3 counts diretos (perfil único)."""
    from .models import TbPerfilCurtida, TbPerfilSeguidor
    pk = _pk(user)
    if not pk:
        return {'curtidas': 0, 'seguidores': 0, 'seguindo': 0}
    return {
        'curtidas': TbPerfilCurtida.objects.filter(alvo_id=pk).count(),
        'seguidores': TbPerfilSeguidor.objects.filter(alvo_id=pk).count(),
        'seguindo': TbPerfilSeguidor.objects.filter(seguidor_id=pk).count(),
    }


def pode_interagir(visitante, alvo):
    """True se `visitante` pode curtir/seguir `alvo`: precisa estar logado e não
    ser o próprio dono do perfil (ninguém curte/segue a si mesmo)."""
    vpk = _pk(visitante)
    apk = _pk(alvo)
    if not vpk or not apk:
        return False
    if not getattr(visitante, 'is_authenticated', False):
        return False
    return vpk != apk


def estado_social(alvo, visitante=None):
    """Dict ÚNICO do social de um perfil, pro template e pro JSON dos endpoints:

        {curtidas, seguidores, seguindo, curtiu, segue, pode_interagir, is_self,
         autenticado}

    `curtiu`/`segue` são sempre False pra visitante anônimo ou pro próprio dono —
    sem botão pra apertar, o estado não existe."""
    from .models import TbPerfilCurtida, TbPerfilSeguidor
    dados = contagens(alvo)
    apk = _pk(alvo)
    vpk = _pk(visitante)
    autenticado = bool(getattr(visitante, 'is_authenticated', False)) and bool(vpk)
    is_self = bool(apk and vpk and apk == vpk)
    interage = pode_interagir(visitante, alvo)
    dados.update({
        'curtiu': (interage and TbPerfilCurtida.objects
                   .filter(quem_id=vpk, alvo_id=apk).exists()),
        'segue': (interage and TbPerfilSeguidor.objects
                  .filter(seguidor_id=vpk, alvo_id=apk).exists()),
        'pode_interagir': interage,
        'is_self': is_self,
        'autenticado': autenticado,
    })
    return dados


# ───────────────────────────── Toggles (idempotentes) ─────────────────────────
def toggle_curtida(quem, alvo):
    """Curte se não curtia, descurte se curtia. Devolve (curtiu_agora, total)."""
    from .models import TbPerfilCurtida
    existente = TbPerfilCurtida.objects.filter(quem=quem, alvo=alvo).first()
    if existente:
        existente.delete()
        curtiu = False
    else:
        # get_or_create absorve o clique duplo/corrida (unique_together no banco).
        TbPerfilCurtida.objects.get_or_create(quem=quem, alvo=alvo)
        curtiu = True
    return curtiu, TbPerfilCurtida.objects.filter(alvo=alvo).count()


def toggle_seguidor(seguidor, alvo):
    """Segue se não seguia, deixa de seguir se seguia. Devolve (segue_agora, total)."""
    from .models import TbPerfilSeguidor
    existente = TbPerfilSeguidor.objects.filter(seguidor=seguidor, alvo=alvo).first()
    if existente:
        existente.delete()
        segue = False
    else:
        TbPerfilSeguidor.objects.get_or_create(seguidor=seguidor, alvo=alvo)
        segue = True
    return segue, TbPerfilSeguidor.objects.filter(alvo=alvo).count()


# ─────────────────────────── Listas simples (meu perfil) ──────────────────────
def _lista_users(qs, campo):
    """[{username, avatar_url, desde}] a partir de um qs de relação, com
    select_related do user + profile (uma query, sem N+1 de avatar)."""
    saida = []
    for rel in qs.select_related(campo, campo + '__profile'):
        u = getattr(rel, campo)
        perfil = getattr(u, 'profile', None)
        saida.append({
            'username': u.username,
            'avatar_url': getattr(perfil, 'avatar_url', '') or '',
            'desde': rel.criado_em,
        })
    return saida


def lista_seguidores(user, limite=50):
    """Quem SEGUE `user` (mais recentes primeiro)."""
    from .models import TbPerfilSeguidor
    if not _pk(user):
        return []
    return _lista_users(TbPerfilSeguidor.objects.filter(alvo=user)[:limite], 'seguidor')


def lista_seguindo(user, limite=50):
    """Quem `user` SEGUE (mais recentes primeiro)."""
    from .models import TbPerfilSeguidor
    if not _pk(user):
        return []
    return _lista_users(TbPerfilSeguidor.objects.filter(seguidor=user)[:limite], 'alvo')


def lista_curtidas(user, limite=50):
    """Quem CURTIU o perfil de `user` (mais recentes primeiro)."""
    from .models import TbPerfilCurtida
    if not _pk(user):
        return []
    return _lista_users(TbPerfilCurtida.objects.filter(alvo=user)[:limite], 'quem')


# ──────────────────────────── Batch (/jogadores/) ─────────────────────────────
def social_counts_batch(users):
    """{user_pk: {'curtidas': n, 'seguidores': n}} pra um conjunto de usuários em
    DUAS queries agregadas — sem N+1 (padrão de badges.perfil_badges_batch)."""
    from .models import TbPerfilCurtida, TbPerfilSeguidor
    users = list(users)
    out = {u.pk: {'curtidas': 0, 'seguidores': 0} for u in users}
    if not users:
        return out
    pks = list(out.keys())
    for row in (TbPerfilCurtida.objects.filter(alvo_id__in=pks)
                .values('alvo_id').annotate(n=Count('id')).order_by()):
        out[row['alvo_id']]['curtidas'] = row['n']
    for row in (TbPerfilSeguidor.objects.filter(alvo_id__in=pks)
                .values('alvo_id').annotate(n=Count('id')).order_by()):
        out[row['alvo_id']]['seguidores'] = row['n']
    return out
