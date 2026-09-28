# -*- coding: utf-8 -*-
"""Badges e títulos do perfil (F2).

Duas fontes de badge, unidas num formato uniforme de dict pros templates:

1. **Derivadas** — computadas na hora a partir do ESTADO do usuário (staff,
   colaborador/apoiador, Mestre Ouro, fundador). Nunca vão pro inventário; não
   dessincronizam. Ver docs/agentes/arquitetura_personalizacao_perfil.md §3.
2. **Concedidas** — o que o usuário POSSUI em TbUsuarioCosmetico com
   cosmetico.tipo='badge' (asset_url = ícone). Entram no inventário via
   conquista/evento/staff.

Títulos (`titulo_do_usuario`) são cosméticos tipo='titulo' equipados por
UserProfile.titulo_equipado, renderizados sob o nome — só valem se o usuário os
possui (cosmetic_allowed), senão None.

Formato uniforme de badge (dict):
    {slug, nome, icone, icone_asset, cor, classe, origem, tooltip, raridade}
- `icone`      : emoji (derivadas) ou '' (concedidas usam icone_asset).
- `icone_asset`: URL do ícone (concedidas) ou '' (derivadas usam emoji).
- `classe`     : classe CSS do pill ('badge-derivada badge-staff' etc.).
- `origem`     : 'derivada' | 'concedida'.

Perf: helpers `_batch` fazem UMA query pro conjunto de usuários da página
(/jogadores/) — sem N+1.
"""
from django.db import transaction
from django.utils import timezone


# Conta criada ATÉ 2026-08-01 (inclusive) ganha a badge de Fundador. Marco fixo:
# quem estava no site na fundação da comunidade. Comparação exclusiva contra o
# início do dia seguinte. Como date_joined pode ser aware (USE_TZ), comparamos por
# .date() — robusto a aware/naive sem depender de settings.
from datetime import date as _date

FUNDADOR_ATE = _date(2026, 8, 1)  # inclusive


# ── Definição visual das badges derivadas (paleta real: ember/flame/spark) ──────
# cor = variável CSS usada pelo pill; classe = modificador CSS.
_DERIVADAS_DEF = {
    'staff': {
        'nome': 'Equipe', 'icone': '🛡️', 'classe': 'badge-staff',
        'tooltip': 'Membro da equipe do Bonfire Tales.',
    },
    'apoiador': {
        'nome': 'Apoiador', 'icone': '🔥', 'classe': 'badge-apoiador',
        'tooltip': 'Colaborador ativo — obrigado por manter a fogueira acesa!',
    },
    'mestre_ouro': {
        'nome': 'Mestre Ouro', 'icone': '⭐', 'classe': 'badge-mestre-ouro',
        'tooltip': 'Assinante Mestre Ouro do Mercado de Mestre.',
    },
    'fundador': {
        'nome': 'Fundador', 'icone': '🕯️', 'classe': 'badge-fundador',
        'tooltip': 'Esteve no Bonfire Tales desde a fundação da comunidade.',
    },
}


def _derivada_dict(slug):
    d = _DERIVADAS_DEF[slug]
    return {
        'slug': slug,
        'nome': d['nome'],
        'icone': d['icone'],
        'icone_asset': '',
        'classe': 'badge-derivada ' + d['classe'],
        'origem': 'derivada',
        'tooltip': d['tooltip'],
        'raridade': 'derivada',
    }


def _is_fundador(user):
    dj = getattr(user, 'date_joined', None)
    if not dj:
        return False
    dj_date = dj.date() if hasattr(dj, 'date') else dj
    return dj_date <= FUNDADOR_ATE


def _slugs_derivadas(user, is_colaborador=None):
    """Conjunto de slugs de badge derivada que o usuário tem AGORA.
    `is_colaborador` pode ser pré-computado (batch); se None, calcula na hora."""
    # AnonymousUser não tem badges. Usuários carregados do banco têm .pk.
    if not user or getattr(user, 'is_anonymous', False):
        return []
    slugs = []
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        slugs.append('staff')
    if is_colaborador is None:
        from .permissions import is_colaborador as _colab
        is_colaborador = _colab(user)
    if is_colaborador:
        slugs.append('apoiador')
    perfil = getattr(user, 'profile', None)
    if getattr(perfil, 'mestre_ouro_ativo', False):
        slugs.append('mestre_ouro')
    if _is_fundador(user):
        slugs.append('fundador')
    return slugs


def badges_derivadas(user, is_colaborador=None):
    """Lista uniforme de badges DERIVADAS (staff/apoiador/mestre_ouro/fundador)."""
    return [_derivada_dict(s) for s in _slugs_derivadas(user, is_colaborador)]


def _concedida_dict(cosmetico):
    """Cosmético tipo='badge' possuído → dict uniforme de badge concedida."""
    rar = cosmetico.get('raridade') if isinstance(cosmetico, dict) else cosmetico.raridade
    slug = cosmetico.get('slug') if isinstance(cosmetico, dict) else cosmetico.slug
    nome = cosmetico.get('nome') if isinstance(cosmetico, dict) else cosmetico.nome
    # Ícone efetivo: arquivo enviado (asset_file) > asset_url/glyph. No dict do
    # catálogo o campo 'asset_url' já vem resolvido (asset_efetivo); no model,
    # usa a property. Preserva a lógica emoji-vs-imagem abaixo.
    asset = (cosmetico.get('asset_url') if isinstance(cosmetico, dict)
             else cosmetico.asset_efetivo)
    desc = cosmetico.get('descricao') if isinstance(cosmetico, dict) else cosmetico.descricao
    # asset_url aceita DUAS formas: URL de imagem (http/https ou caminho /static…) →
    # renderiza <img>; ou um glyph emoji (ex.: '🐉') → renderiza como texto nativo,
    # sem depender de CDN externo. Vazio → medalha genérica.
    _asset = (asset or '').strip()
    _is_url = _asset.startswith(('http://', 'https://', '/'))
    return {
        'slug': slug,
        'nome': nome,
        'icone': '' if _is_url else (_asset or '🏅'),
        'icone_asset': _asset if _is_url else '',
        'classe': 'badge-concedida badge-rar-%s' % (rar or 'comum'),
        'origem': 'concedida',
        'tooltip': desc or nome,
        'raridade': rar or 'comum',
    }


def _badges_concedidas_qs(user):
    from .models import TbUsuarioCosmetico
    return (TbUsuarioCosmetico.objects
            .filter(user=user, cosmetico__tipo='badge', cosmetico__ativo=True,
                    suspenso_em__isnull=True)
            .select_related('cosmetico')
            .order_by('cosmetico__ordem', 'cosmetico__nome'))


def badges_concedidas(user):
    """Badges que o usuário POSSUI (inventário, tipo='badge')."""
    if not user or not getattr(user, 'pk', None):
        return []
    return [_concedida_dict(uc.cosmetico) for uc in _badges_concedidas_qs(user)]


def _ordena_por_destaque(badges, destaque_slugs):
    """As badges fixadas (badges_destaque) primeiro, na ordem em que o usuário fixou;
    o resto depois, na ordem natural. `destaque_slugs` é lista de slugs."""
    if not destaque_slugs:
        return badges
    por_slug = {b['slug']: b for b in badges}
    destaque, resto = [], []
    vistos = set()
    for slug in destaque_slugs:
        b = por_slug.get(slug)
        if b and slug not in vistos:
            destaque.append(b)
            vistos.add(slug)
    for b in badges:
        if b['slug'] not in vistos:
            resto.append(b)
    return destaque + resto


def badges_com_destaque(user, destaque_slugs, is_colaborador=None, ocultas_derivadas=None):
    """Derivadas + concedidas do usuário, com as fixadas em `destaque_slugs` primeiro.

    Caminho ÚNICO de montagem da vitrine: o perfil público passa o que está SALVO
    (UserProfile.badges_destaque) e a prévia viva passa o candidato do formulário
    (já filtrado por posse em _validated_badges_destaque) — mesmo código, zero drift."""
    if not user or not getattr(user, 'pk', None):
        return []
    ocultas = set(ocultas_derivadas or []) - {'staff'}
    derivadas = [b for b in badges_derivadas(user, is_colaborador)
                 if b['slug'] not in ocultas]
    concedidas = badges_concedidas(user)
    # Fixadas primeiro (dentre TODAS as badges), preservando derivadas na frente.
    return _ordena_por_destaque(derivadas + concedidas, list(destaque_slugs or []))


def badges_do_usuario(user, is_colaborador=None):
    """Derivadas + concedidas, com as FIXADAS (badges_destaque) primeiro.
    As derivadas vêm sempre na frente das concedidas não-fixadas."""
    perfil = getattr(user, 'profile', None)
    destaque = list(getattr(perfil, 'badges_destaque', None) or [])
    ocultas = list(getattr(perfil, 'badges_derivadas_ocultas', None) or [])
    return badges_com_destaque(user, destaque, is_colaborador, ocultas)


def user_possui_cosmetico(user, slug, tipo):
    """True se o usuário POSSUI o cosmético de `slug` exato (tipo dado). Checa
    inventário por SLUG COMPLETO (blindado ao esquema de prefixos do catálogo de
    aparência) OU cosmético origem='livre' (todos têm)."""
    if not user or not getattr(user, 'pk', None) or not slug:
        return False
    from .models import TbCosmetico, TbUsuarioCosmetico
    cos = TbCosmetico.objects.filter(tipo=tipo, slug=slug, ativo=True).first()
    if not cos:
        return False
    if cos.origem == 'livre':
        return True
    return TbUsuarioCosmetico.objects.filter(
        user=user, cosmetico=cos, suspenso_em__isnull=True).exists()


def _titulo_dict(cos):
    """Cosmético tipo='titulo' → dict uniforme pro template (formato ÚNICO)."""
    return {
        'slug': cos.slug,
        'nome': cos.nome,
        'raridade': cos.raridade or 'comum',
        'classe': 'profile-title rar-%s' % (cos.raridade or 'comum'),
        'descricao': cos.descricao or '',
    }


def titulo_por_slug(user, slug):
    """Dict do título de `slug` SE o usuário o possui; senão None.

    Caminho ÚNICO de resolução de título: o perfil público passa o slug SALVO e a
    prévia viva passa o slug candidato do formulário (já filtrado por posse em
    _validated_titulo_equipado). Um slug não-possuído devolve None nos dois casos."""
    slug = (slug or '').strip()
    if not user or not getattr(user, 'pk', None) or not slug:
        return None
    if not user_possui_cosmetico(user, slug, 'titulo'):
        return None
    from .models import TbCosmetico
    cos = TbCosmetico.objects.filter(tipo='titulo', slug=slug, ativo=True).first()
    return _titulo_dict(cos) if cos else None


def titulo_do_usuario(user):
    """Cosmético tipo='titulo' equipado (UserProfile.titulo_equipado) que o usuário
    POSSUI. Retorna dict {slug, nome, raridade, classe, descricao} ou None."""
    perfil = getattr(user, 'profile', None)
    return titulo_por_slug(user, getattr(perfil, 'titulo_equipado', ''))


def titulos_disponiveis(user):
    """Lista de títulos que o usuário POSSUI (pro dropdown de edição). Dicts
    {slug, nome, raridade}. Sempre inclui a opção implícita 'nenhum' no template."""
    if not user or not getattr(user, 'pk', None):
        return []
    from .models import TbUsuarioCosmetico
    qs = (TbUsuarioCosmetico.objects
          .filter(user=user, cosmetico__tipo='titulo', cosmetico__ativo=True,
                  suspenso_em__isnull=True)
          .select_related('cosmetico')
          .order_by('cosmetico__ordem', 'cosmetico__nome'))
    return [{'slug': uc.cosmetico.slug, 'nome': uc.cosmetico.nome,
             'raridade': uc.cosmetico.raridade or 'comum'} for uc in qs]


# ──────────────────────────── Batch (/jogadores/) ──────────────────────────────
def is_colaborador_batch(users):
    """Mapa {user_pk: bool} de colaborador ativo para um conjunto de usuários, em
    UMA query na tabela `transactions` do bot. Evita N chamadas de is_colaborador.
    Default: todos False se a tabela do bot estiver ausente (SQLite dev)."""
    resultado = {u.pk: False for u in users}
    try:
        # As tabelas do bot são opcionais em dev/teste. O ``atomic`` interno cria
        # um savepoint quando a view já está em transação; se a tabela não existe,
        # o rollback fica restrito a esta leitura e as consultas seguintes seguem.
        with transaction.atomic():
            return _is_colaborador_batch_from_bot(users, resultado)
    except Exception:
        return resultado


def _is_colaborador_batch_from_bot(users, resultado):
    from django.db.models import Q
    from .models import BotTransaction, BotMember

    # e-mail direto do auth.User + e-mails ligados via discord_user_id do perfil.
    email_para_pks = {}
    did_para_pks = {}
    for u in users:
        email = (getattr(u, 'email', '') or '').strip().lower()
        if email:
            email_para_pks.setdefault(email, []).append(u.pk)
        perfil = getattr(u, 'profile', None)
        did = getattr(perfil, 'discord_user_id', None)
        if did:
            did_para_pks.setdefault(str(did), []).append(u.pk)
    # discord_user_id → e-mails do BotMember (uma query).
    if did_para_pks:
        membros = BotMember.objects.filter(
            discordUserId__in=list(did_para_pks.keys())
        ).values_list('discordUserId', 'email')
        for did, email in membros:
            if email:
                for pk in did_para_pks.get(str(did), []):
                    email_para_pks.setdefault(email.strip().lower(), []).append(pk)
    if not email_para_pks:
        return resultado
    cond = Q()
    for email in email_para_pks:
        cond |= Q(email__iexact=email)
    ativos = (BotTransaction.objects
              .filter(cond, subscriptionPlan__startswith='colaborador',
                      status=1, expirationDate__gt=timezone.now())
              .values_list('email', flat=True))
    for email in ativos:
        for pk in email_para_pks.get((email or '').strip().lower(), []):
            resultado[pk] = True
    return resultado


def _badges_concedidas_batch(users):
    """Mapa {user_pk: [badge_dict, ...]} das badges CONCEDIDAS de vários usuários,
    em UMA query (tipo='badge')."""
    from .models import TbUsuarioCosmetico
    out = {u.pk: [] for u in users}
    if not users:
        return out
    qs = (TbUsuarioCosmetico.objects
          .filter(user_id__in=[u.pk for u in users],
                  cosmetico__tipo='badge', cosmetico__ativo=True,
                  suspenso_em__isnull=True)
          .select_related('cosmetico')
          .order_by('cosmetico__ordem', 'cosmetico__nome'))
    for uc in qs:
        out.setdefault(uc.user_id, []).append(_concedida_dict(uc.cosmetico))
    return out


def _titulos_equipados_batch(users):
    """Mapa {user_pk: titulo_dict|None} dos títulos equipados, validando posse em
    UMA query no inventário (tipo='titulo'). Só devolve título que o usuário POSSUI."""
    from .models import TbUsuarioCosmetico, TbCosmetico
    out = {u.pk: None for u in users}
    # slug de título desejado por usuário (do UserProfile.titulo_equipado).
    desejado = {}
    for u in users:
        perfil = getattr(u, 'profile', None)
        slug = (getattr(perfil, 'titulo_equipado', '') or '').strip()
        if slug:
            desejado[u.pk] = slug
    if not desejado:
        return out
    slugs = set(desejado.values())
    # Cosméticos de título ativos com esses slugs (uma query).
    cos_por_slug = {c.slug: c for c in TbCosmetico.objects.filter(
        tipo='titulo', ativo=True, slug__in=slugs)}
    # Posse: quais (user, slug) existem no inventário (uma query).
    possui = set(TbUsuarioCosmetico.objects.filter(
        user_id__in=list(desejado.keys()),
        cosmetico__tipo='titulo', cosmetico__ativo=True,
        suspenso_em__isnull=True,
        cosmetico__slug__in=slugs
    ).values_list('user_id', 'cosmetico__slug'))
    for pk, slug in desejado.items():
        cos = cos_por_slug.get(slug)
        if cos and (pk, slug) in possui:
            out[pk] = _titulo_dict(cos)
    return out


def perfil_badges_batch(users):
    """Pro /jogadores/: {user_pk: {'badges': [...], 'titulo': dict|None}} com no
    máximo 3 queries no total (colaborador + badges concedidas + títulos), sem N+1.
    As badges já vêm ordenadas com as fixadas (badges_destaque) primeiro."""
    users = list(users)
    if not users:
        return {}
    colab_map = is_colaborador_batch(users)
    concedidas_map = _badges_concedidas_batch(users)
    titulos_map = _titulos_equipados_batch(users)
    out = {}
    for u in users:
        perfil = getattr(u, 'profile', None)
        destaque = list(getattr(perfil, 'badges_destaque', None) or [])
        ocultas = set(getattr(perfil, 'badges_derivadas_ocultas', None) or []) - {'staff'}
        derivadas = [b for b in badges_derivadas(u, colab_map.get(u.pk, False))
                     if b['slug'] not in ocultas]
        concedidas = concedidas_map.get(u.pk, [])
        badges = _ordena_por_destaque(derivadas + concedidas, destaque)
        out[u.pk] = {'badges': badges, 'titulo': titulos_map.get(u.pk)}
    return out
