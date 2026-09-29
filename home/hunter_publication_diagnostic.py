"""Resolve the published Hunter once for the public page and protected status."""
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError
from django.utils.text import slugify


class HunterPublicationUnavailable(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def resolve_publication():
    """Return only a fully reviewed catalog; never fall back to live legacy rows."""
    from .content_versions import resolve_content
    from .hunter_regularization import _reviewed_target, _target_orders
    from .models import TbClasse, TbRecursoclasse, TbRuleset
    from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog

    checksum = settings.HUNTER_CREATOR_RULESET_CHECKSUM
    if not checksum:
        raise HunterPublicationUnavailable('config_missing')
    try:
        ruleset = TbRuleset.objects.get(checksum=checksum)
    except TbRuleset.DoesNotExist as exc:
        raise HunterPublicationUnavailable('ruleset_missing') from exc
    try:
        live = TbClasse.objects.get(slug='cacador')
    except TbClasse.DoesNotExist as exc:
        raise HunterPublicationUnavailable('class_missing') from exc
    try:
        catalog = VersionedClassCatalog(ruleset, live.pk)
        if catalog.classe.slug != 'cacador':
            raise ValueError('Invalid class identity')
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist) as exc:
        raise HunterPublicationUnavailable('class_snapshot_invalid') from exc
    try:
        data = resolve_content(ruleset, 'hunter-rework',
                               evaluator_version=EVALUATOR,
                               vocabulary_version=VOCABULARY)
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist) as exc:
        raise HunterPublicationUnavailable('rework_snapshot_invalid') from exc
    try:
        if not _reviewed_target(ruleset, live.pk, data):
            raise HunterPublicationUnavailable('review_incomplete')
        orders = _target_orders(ruleset, catalog, applying=True)
        expected = {slugify(row['name']) for row in data['orders']}
        if len(orders) != 8 or {slugify(row.nome) for row in orders.values()} != expected:
            raise HunterPublicationUnavailable('orders_incomplete')
        progression = {row['level']: row for row in data['progression']}
        if (set(progression) != set(range(1, 21)) or
                any(not row.get('features') or not row.get('hunter_die')
                    for row in progression.values())):
            raise HunterPublicationUnavailable('progression_incomplete')
        dice = [row for row in catalog.collections[TbRecursoclasse]
                if row.id_subclasse_id is None and
                slugify(row.nome).startswith('dado-de-ca')]
        if len(dice) != 1:
            raise HunterPublicationUnavailable('hunter_die_incomplete')
    except (ValueError, KeyError, TypeError, ObjectDoesNotExist) as exc:
        raise HunterPublicationUnavailable('catalog_invalid') from exc
    return {'class': catalog.classe, 'catalog': catalog, 'orders': orders,
            'progression': progression, 'hunter_die_resource_id': dice[0].pk}


def publication_status():
    """Read-only, minimal status; no personal data, SQL or internal traceback."""
    checksum = settings.HUNTER_CREATOR_RULESET_CHECKSUM
    status = {'schema': 1, 'published': False, 'code': 'config_missing',
              'checksum_prefix': checksum[:12] if checksum else None}
    try:
        resolved = resolve_publication()
    except HunterPublicationUnavailable as exc:
        status['code'] = exc.code
        return status
    except DatabaseError:
        status['code'] = 'database_unavailable'
        return status
    status.update(published=True, code='ok', orders=len(resolved['orders']),
                  levels=len(resolved['progression']))
    return status
