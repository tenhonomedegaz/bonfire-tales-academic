"""Minimal, read-only status for the published Hunter catalog."""
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.text import slugify


def publication_status():
    from .content_versions import resolve_content
    from .hunter_regularization import _reviewed_target, _target_orders
    from .models import TbClasse, TbRecursoclasse, TbRuleset
    from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog

    checksum = settings.HUNTER_CREATOR_RULESET_CHECKSUM
    status = {'schema': 1, 'published': False, 'code': 'config_missing',
              'checksum_prefix': checksum[:12] if checksum else None}
    if not checksum:
        return status
    try:
        ruleset = TbRuleset.objects.get(checksum=checksum)
    except TbRuleset.DoesNotExist:
        status['code'] = 'ruleset_missing'
        return status
    try:
        live = TbClasse.objects.get(slug='cacador')
    except TbClasse.DoesNotExist:
        status['code'] = 'class_missing'
        return status
    try:
        catalog = VersionedClassCatalog(ruleset, live.pk)
        if catalog.classe.slug != 'cacador':
            raise ValueError('Invalid class identity')
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist):
        status['code'] = 'class_snapshot_invalid'
        return status
    try:
        data = resolve_content(ruleset, 'hunter-rework',
                               evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY)
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist):
        status['code'] = 'rework_snapshot_invalid'
        return status
    try:
        if not _reviewed_target(ruleset, live.pk, data):
            status['code'] = 'review_incomplete'
            return status
        orders = _target_orders(ruleset, catalog, applying=True)
        expected = {slugify(row['name']) for row in data['orders']}
        if len(orders) != 8 or {slugify(row.nome) for row in orders.values()} != expected:
            status['code'] = 'orders_incomplete'
            return status
        progression = {row['level']: row for row in data['progression']}
        if (set(progression) != set(range(1, 21)) or
                any(not row.get('features') or not row.get('hunter_die')
                    for row in progression.values())):
            status['code'] = 'progression_incomplete'
            return status
        dice = [row for row in catalog.collections[TbRecursoclasse]
                if row.id_subclasse_id is None and
                slugify(row.nome).startswith('dado-de-ca')]
        if len(dice) != 1:
            status['code'] = 'hunter_die_incomplete'
            return status
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist):
        status['code'] = 'catalog_invalid'
        return status
    status.update(published=True, code='ok', orders=8, levels=20)
    return status
