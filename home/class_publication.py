"""One reviewed publication pointer per class, independent of class names."""
import re
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import connection, transaction
from django.utils import timezone

from .models import TbClassPublication, TbClassPublicationLog, TbClasse, TbRuleset
from .versioned_classes import VersionedClassCatalog


class ClassPublicationConflict(Exception):
    pass


CATALOG_ERRORS = (ObjectDoesNotExist, ValueError, KeyError, TypeError,
                  AttributeError, IndexError, OverflowError, RecursionError)
_UNRESOLVED = object()


@dataclass(frozen=True)
class ClassCatalogSelection:
    mode: str
    ruleset: object = None
    catalog: object = None


def _validated_catalog(ruleset, classe, *, require_presentation=False):
    catalog = VersionedClassCatalog(ruleset, classe.pk)
    if (catalog.classe.slug != classe.slug or
            require_presentation and catalog.presentation_source != 'catalog'):
        raise ValueError('Invalid class identity or presentation contract.')
    for rows in catalog.collections.values():
        ids = [row.pk for row in rows]
        if any(type(pk) is not int or pk < 1 for pk in ids) or len(set(ids)) != len(ids):
            raise ValueError('Invalid source identities in class catalog.')
    return catalog


def resolve_class_catalog(classe, *, publication=_UNRESOLVED):
    """Select pointer -> configured snapshot -> source, without changing pins.

    A caller that already read the pointer may pass that result (including None).
    Invalid selected snapshots raise; only an absent selection permits source.
    Configured legacy snapshots need not declare the common presentation contract.
    Compatibility aliases belong in settings, not class-specific reader branches.
    """
    if publication is _UNRESOLVED:
        publication = published_catalog(classe)
    if publication is not None:
        return ClassCatalogSelection('published', *publication)
    bindings = getattr(settings, 'CLASS_CATALOG_RULESETS', {})
    if not isinstance(bindings, dict):
        raise ValueError('Invalid configured catalog mapping.')
    if classe.slug not in bindings:
        return ClassCatalogSelection('source')
    checksum = bindings[classe.slug]
    if not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
        raise ValueError('Invalid configured catalog checksum.')
    ruleset = TbRuleset.objects.get(checksum=checksum)
    catalog = _validated_catalog(ruleset, classe)
    return ClassCatalogSelection('configured', ruleset, catalog)


def published_catalog(classe):
    """Resolve the class's current immutable catalog, or None when unpublished."""
    binding = TbClassPublication.objects.select_related('ruleset').filter(
        id_classe_id=classe.pk).first()
    if binding is None:
        return None
    catalog = _validated_catalog(binding.ruleset, classe, require_presentation=True)
    return binding.ruleset, catalog


def publication_preview(class_id, target_checksum, expected_current):
    """Read-only preflight; counts come from the snapshot, never a class constant."""
    from .models import TbClassehabilidade, TbSubclasse

    classe = TbClasse.objects.get(pk=class_id)
    target = TbRuleset.objects.get(checksum=target_checksum)
    catalog = _validated_catalog(target, classe, require_presentation=True)
    current = TbClassPublication.objects.filter(id_classe_id=class_id).select_related('ruleset').first()
    current_checksum = current.ruleset.checksum if current else 'unpublished'
    if expected_current != current_checksum:
        raise ClassPublicationConflict('Published version changed.')
    return {'class_id': class_id, 'target_checksum': target.checksum,
            'current_checksum': current_checksum,
            'subclasses': len(catalog.collections[TbSubclasse]),
            'features': len(catalog.collections[TbClassehabilidade]),
            'already_published': current_checksum == target.checksum}


@transaction.atomic
def publish_class(class_id, target_checksum, expected_current, *, actor_key_id=None):
    """Activate after a verified server-side backup, with an auditable pointer change."""
    from .content_maintenance import _fresh_backup, _local_postgres, _protected_directory

    if not _local_postgres():
        raise ValueError('Local PostgreSQL is required for publication.')
    TbClasse.objects.select_for_update().get(pk=class_id)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [0x424F4E46, class_id])
    preview = publication_preview(class_id, target_checksum, expected_current)
    if preview['already_published']:
        return preview
    folder = _protected_directory()
    _fresh_backup(folder, 'class-%s' % class_id)
    target = TbRuleset.objects.get(checksum=target_checksum)
    binding = TbClassPublication.objects.select_for_update().filter(id_classe_id=class_id).first()
    previous = binding.ruleset if binding else None
    if binding is None:
        TbClassPublication.objects.create(id_classe_id=class_id, ruleset=target)
    else:
        binding.ruleset = target
        binding.published_at = timezone.now()
        binding.save(update_fields=['ruleset', 'published_at'])
    TbClassPublicationLog.objects.create(
        id_classe_id=class_id, previous_ruleset=previous, new_ruleset=target,
        actor_key_id=actor_key_id)
    return {**preview, 'already_published': False, 'published': True}


def class_publication_preview_operation(payload, api_key):
    from .db_access import ApiProblem
    if set(payload) != {'base_version', 'class_id', 'target_checksum'} or type(payload['class_id']) is not int:
        raise ApiProblem(400, 'invalid_publication', 'Prévia de publicação inválida.')
    try:
        return publication_preview(payload['class_id'], payload['target_checksum'], payload['base_version'])
    except ClassPublicationConflict:
        raise ApiProblem(409, 'publication_conflict', 'A revisão publicada mudou.') from None
    except (TbClasse.DoesNotExist, TbRuleset.DoesNotExist):
        raise ApiProblem(404, 'publication_target_missing', 'Classe ou revisão não encontrada.') from None
    except (ValueError, KeyError, TypeError):
        raise ApiProblem(400, 'invalid_publication', 'Revisão de classe inválida.') from None


def class_publication_operation(payload, api_key):
    from .db_access import ApiProblem
    if set(payload) != {'base_version', 'class_id', 'target_checksum'} or type(payload['class_id']) is not int:
        raise ApiProblem(400, 'invalid_publication', 'Publicação inválida.')
    try:
        return publish_class(payload['class_id'], payload['target_checksum'], payload['base_version'],
                             actor_key_id=api_key.pk)
    except ClassPublicationConflict:
        raise ApiProblem(409, 'publication_conflict', 'A revisão publicada mudou.') from None
    except (TbClasse.DoesNotExist, TbRuleset.DoesNotExist):
        raise ApiProblem(404, 'publication_target_missing', 'Classe ou revisão não encontrada.') from None
    except (ValueError, KeyError, TypeError, OSError):
        raise ApiProblem(400, 'publication_preflight_failed', 'Preflight ou backup falhou.') from None
