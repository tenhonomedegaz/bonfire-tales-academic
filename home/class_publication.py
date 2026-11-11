"""One reviewed publication pointer per class, independent of class names."""
from django.db import connection, transaction
from django.utils import timezone

from .models import TbClassPublication, TbClassPublicationLog, TbClasse, TbRuleset
from .versioned_classes import VersionedClassCatalog


class ClassPublicationConflict(Exception):
    pass


def published_catalog(classe):
    """Resolve the class's current immutable catalog, or None when unpublished."""
    binding = TbClassPublication.objects.select_related('ruleset').filter(
        id_classe_id=classe.pk).first()
    if binding is None:
        return None
    catalog = VersionedClassCatalog(binding.ruleset, classe.pk)
    if catalog.classe.slug != classe.slug or catalog.presentation_source != 'catalog':
        raise ValueError('Invalid published class identity or presentation contract.')
    return binding.ruleset, catalog


def publication_preview(class_id, target_checksum, expected_current):
    """Read-only preflight; counts come from the snapshot, never a class constant."""
    from .models import TbClassehabilidade, TbSubclasse

    classe = TbClasse.objects.get(pk=class_id)
    target = TbRuleset.objects.get(checksum=target_checksum)
    catalog = VersionedClassCatalog(target, class_id)
    if catalog.classe.slug != classe.slug or catalog.presentation_source != 'catalog':
        raise ValueError('Target catalog is not ready for common publication.')
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
