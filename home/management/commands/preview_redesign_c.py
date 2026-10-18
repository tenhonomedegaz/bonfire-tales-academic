"""Read-only reconciliation of existing character-slot rights for G01-C."""

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.conquistas import _marcos_rank_comprovados
from home.mestre_ouro import has_unreconciled_mestre_ouro_history
from home.models import (MestreOuroDireito, MestreOuroRevisao, TbConquista,
                         TbEventoConquista, TbPersonagem, TbTransacaoMestre,
                         TbUsuarioConquista, UserProfile)

MILESTONE_LEVELS = (5, 9, 13, 20)


def configured_level_achievements():
    """Expose existing site milestone definitions without inferring token policy."""
    rows = []
    definitions = TbConquista.objects.filter(
        criterio='automatico', criterio_json__metric='character_level',
    ).prefetch_related('recompensas_extras').order_by('pk')
    for achievement in definitions.iterator(chunk_size=200):
        rule = achievement.criterio_json or {}
        if not isinstance(rule, dict):
            continue
        level = rule.get('target')
        if type(level) is not int or level not in MILESTONE_LEVELS:
            continue
        filters = rule.get('filters') or {}
        if not isinstance(filters, dict):
            filters = {}
        rows.append({
            'id': achievement.pk,
            'slug': achievement.slug,
            'level': level,
            'class_slug': filters.get('class_slug'),
            'single_class': filters.get('single_class') is True,
            'active': achievement.ativo,
            'cosmetic_reward_ids': sorted({
                *achievement.recompensas_extras.values_list('pk', flat=True),
                *([achievement.recompensa_id] if achievement.recompensa_id else []),
            }),
            'active_grants': TbUsuarioConquista.objects.filter(
                conquista=achievement, revogada_em__isnull=True,
            ).count(),
        })
    return rows


def preview():
    """Classify candidates; a level alone never grants a right here."""
    owners = set(TbPersonagem.objects.filter(nivel__gte=5).values_list('dono_id', flat=True))
    owners.update(MestreOuroDireito.objects.values_list('user_id', flat=True))
    owners.update(MestreOuroRevisao.objects.values_list('user_id', flat=True))
    owners.update(UserProfile.objects.filter(mestre_ouro_ativo=True).values_list('user_id', flat=True))
    owners.update(TbEventoConquista.objects.filter(
        origem='site', tipo='character_level_up', payload_json__level_after__gte=5,
    ).values_list('conta_id', flat=True))
    owners.update(TbTransacaoMestre.objects.filter(
        tipo__in=('assinatura', 'mensalidade'), valor_mm__lt=0,
    ).values_list('mestre_id', flat=True))
    owners.update(TbTransacaoMestre.objects.filter(
        tipo='resgate', descricao__icontains='Slot permanente de personagem',
        valor_mm__lt=0,
    ).values_list('mestre_id', flat=True))
    rows = []
    for user in get_user_model().objects.filter(pk__in=owners).order_by('pk').iterator():
        levels = list(TbPersonagem.objects.filter(dono=user, nivel__gte=5)
                      .order_by('-nivel', 'pk').values_list('nivel', flat=True))
        proven = _marcos_rank_comprovados(user)
        profile = UserProfile.objects.filter(user=user).first()
        lifetime_right = MestreOuroDireito.objects.filter(user=user).exists()
        milestone_candidates = {
            f'current_level_{level}_candidate': any(value >= level for value in levels)
            for level in MILESTONE_LEVELS
        }
        milestone_proof = {
            f'proven_level_{level}': any(value >= level for value, _ in proven)
            for level in MILESTONE_LEVELS
        }
        rows.append({
            'user_id': user.pk,
            **milestone_candidates,
            **milestone_proof,
            'existing_lifetime_slot': lifetime_right,
            'legacy_gold_review_needed': has_unreconciled_mestre_ouro_history(user.pk, profile),
            'slot_redemption_without_right': (
                not lifetime_right
                and TbTransacaoMestre.objects.filter(
                    mestre=user, tipo='resgate',
                    descricao__icontains='Slot permanente de personagem', valor_mm__lt=0,
                ).exists()),
        })
    return rows


class Command(BaseCommand):
    help = 'Preview G01-C level candidates and existing slot rights; never grants or debits.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('G01-C inventory requires PostgreSQL.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            rows = preview()
            achievements = configured_level_achievements()
        settings = connection.settings_dict
        self.stdout.write(json.dumps({
            'policy': 'levels 5/9/13/20 are candidates only; this command never grants',
            'database': {key: str(settings.get(key) or '')
                         for key in ('ENGINE', 'NAME', 'HOST', 'PORT', 'USER')},
            'count': len(rows), 'accounts': rows,
            'configured_level_achievements': achievements,
            'configuration_note': ('Site achievements disclose cosmetic rewards only; '
                                   'token and character-slot policy is not inferred.'),
        }, ensure_ascii=False, sort_keys=True))
