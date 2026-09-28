"""Pinned condition labels used by passive immunity rendering."""
from .models import TbCondicao
from .content_versions import create_revision, resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY


def snapshot_conditions(*, author=None):
    return create_revision('condition-catalog', {'schema': 1, 'names': {
        c.slug: c.nome for c in TbCondicao.objects.order_by('pk')}}, author=author)


def condition_names(ruleset):
    data = resolve_content(ruleset, 'condition-catalog', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    names = data.get('names')
    if data.get('schema') != 1 or not isinstance(names, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in names.items()):
        raise ValueError('Invalid pinned condition catalog.')
    return names
