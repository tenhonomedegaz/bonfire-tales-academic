"""Seal and resolve content independently of the mutable catalog.

No character activation is exposed until all engine consumers support this resolver.
"""
import copy
import hashlib
import json

from django.db import transaction

from .models import TbContentRevision, TbRuleset, TbRulesetContent


def digest(payload):
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def create_revision(identity, payload, *, dependencies=(), author=None):
    if not isinstance(identity, str) or not identity.strip() or len(identity) > 200:
        raise ValueError('Invalid content identity.')
    if not isinstance(payload, dict) or any(not isinstance(d, str) or not d for d in dependencies):
        raise ValueError('Invalid revision payload or dependencies.')
    dependencies = sorted(set(dependencies))
    checksum = digest({'identity': identity, 'payload': payload, 'dependencies': dependencies})
    revision, _ = TbContentRevision.objects.get_or_create(
        identity=identity, checksum=checksum,
        defaults={'payload': copy.deepcopy(payload), 'dependencies': dependencies, 'author': author})
    return revision


@transaction.atomic
def seal_ruleset(revisions, *, evaluator_version, vocabulary_version, author=None):
    if not evaluator_version or not vocabulary_version:
        raise ValueError('Evaluator and vocabulary versions are mandatory.')
    revisions = list(revisions)
    ids = [r.pk for r in revisions]
    rows = list(TbContentRevision.objects.filter(pk__in=ids).order_by('identity'))
    if not rows or len(rows) != len(ids) or len({r.identity for r in rows}) != len(rows):
        raise ValueError('Missing or duplicate content identity.')
    identities = {r.identity for r in rows}
    for revision in rows:
        if set(revision.dependencies) - identities:
            raise ValueError('Unresolved dependencies for %s.' % revision.identity)
        if revision.checksum != digest({'identity': revision.identity, 'payload': revision.payload,
                                        'dependencies': revision.dependencies}):
            raise ValueError('Corrupted revision.')
    manifest = {r.identity: r.checksum for r in rows}
    checksum = digest({'manifest': manifest, 'evaluator': evaluator_version,
                       'vocabulary': vocabulary_version})
    ruleset, created = TbRuleset.objects.get_or_create(checksum=checksum, defaults={
        'manifest': manifest, 'evaluator_version': evaluator_version,
        'vocabulary_version': vocabulary_version, 'author': author})
    if created:
        TbRulesetContent.objects.bulk_create([
            TbRulesetContent(ruleset=ruleset, revision=r, identity=r.identity) for r in rows])
    return ruleset


def resolve_content(ruleset, identity, *, evaluator_version, vocabulary_version):
    # Refuse unsupported semantics instead of silently reading current catalog content.
    current = TbRuleset.objects.get(pk=ruleset.pk)
    if (current.evaluator_version, current.vocabulary_version) != (evaluator_version, vocabulary_version):
        raise ValueError('Unsupported ruleset semantics.')
    if current.checksum != digest({'manifest': current.manifest,
                                  'evaluator': current.evaluator_version,
                                  'vocabulary': current.vocabulary_version}):
        raise ValueError('Corrupted ruleset.')
    entry = current.entries.select_related('revision').get(identity=identity)
    revision = entry.revision
    expected = digest({'identity': revision.identity, 'payload': revision.payload,
                       'dependencies': revision.dependencies})
    if identity != revision.identity or current.manifest.get(identity) != expected or revision.checksum != expected:
        raise ValueError('Corrupted content binding.')
    return copy.deepcopy(revision.payload)
