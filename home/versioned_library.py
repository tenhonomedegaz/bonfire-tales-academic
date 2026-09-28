"""Explicit immutable vocabulary context for character calculations."""
from contextlib import contextmanager
from .content_versions import create_revision, resolve_content
from .versioned_classes import EVALUATOR, VOCABULARY
from .tag_engine.library import Library, library_scope


def snapshot_library(*, raw, author=None):
    # Caller supplies the reviewed vocabulary; never silently capture a DB fallback.
    library = Library(raw=raw)
    return create_revision('tag-library', {'schema': 1, 'library': library.raw}, author=author)


@contextmanager
def ruleset_evaluation(ruleset):
    data = resolve_content(ruleset, 'tag-library', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    if data.get('schema') != 1 or not isinstance(data.get('library'), dict):
        raise ValueError('Unsupported pinned tag library.')
    with library_scope(data['library']):
        yield
