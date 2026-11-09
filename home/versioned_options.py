"""Frozen option universes, including global ACL presence and explicit origins."""
from copy import deepcopy

from django.db import transaction
from django.utils.text import slugify

from .content_versions import create_revision, resolve_content
from .models import TbOpcaojogo, TbAcessoopcao, TbClasse, TbSubclasse
from .versioned_classes import EVALUATOR, VOCABULARY, _fields

IDENTITY = 'option-catalog'


@transaction.atomic
def snapshot_options(*, author=None):
    # Preparation only. Publication must serialize catalog writers.
    payload = {
        'schema': 1,
        'options': [_fields(o) for o in TbOpcaojogo.objects.order_by('pk')],
        'access': [_fields(a) for a in TbAcessoopcao.objects.order_by('pk')],
        'classes': list(TbClasse.objects.order_by('pk').values('id_classe', 'slug')),
        'subclasses': list(TbSubclasse.objects.order_by('pk').values(
            'id_subclasse', 'id_classe_id', 'slug')),
    }
    return create_revision(IDENTITY, payload, author=author)


class VersionedOptions:
    def __init__(self, ruleset):
        self.data = deepcopy(resolve_content(ruleset, IDENTITY,
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY))
        if self.data.get('schema') != 1:
            raise ValueError('Unsupported option snapshot.')
        for key, model in (('options', TbOpcaojogo), ('access', TbAcessoopcao)):
            fields = {f.attname for f in model._meta.concrete_fields}
            if model is TbOpcaojogo:
                for row in self.data[key]:
                    # Old sealed revisions predate the editorial archive flag.
                    if set(row) == fields - {'arquivado'}:
                        row['arquivado'] = False
            if any(set(row) != fields for row in self.data[key]):
                raise ValueError('Incompatible option snapshot fields.')
        ids = {o['id_opcao'] for o in self.data['options']}
        if any(a['id_opcao_id'] not in ids for a in self.data['access']):
            raise ValueError('Missing option referenced by access rule.')

    def type_map(self):
        out = {}
        for o in self.data['options']:
            name = o['tipo']
            if name and not o['arquivado']:
                slug = slugify(name)
                out[slug] = out[slug.replace('-', '_')] = name
        return out

    def universe(self, ctx):
        tipo = ctx.get('tipo_display') or self.type_map().get(ctx['tipo'])
        classe = getattr(ctx.get('classe'), 'pk', None)
        subclasse = getattr(ctx.get('subclasse'), 'pk', None)
        constraints = ctx.get('constraints') or {}
        listed = constraints.get('listed_slugs')
        kind, slug = constraints.get('from_kind'), constraints.get('from_slug')
        explicit = bool(kind and slug)
        if kind == 'classe':
            classe = next((c['id_classe'] for c in self.data['classes'] if c['slug'] == slug), None)
            subclasse = None
        elif kind == 'subclasse':
            sub = next((s for s in self.data['subclasses'] if s['slug'] == slug), None)
            subclasse = sub['id_subclasse'] if sub else None
            classe = sub['id_classe_id'] if sub else None
        options = [o for o in self.data['options'] if o['tipo'] == tipo and not o['arquivado']]
        if listed:
            options = [o for o in options if o['slug'].replace('_', '-') in listed]
            return [{'id': o['id_opcao'], 'slug': o['slug'], 'nome': o['nome'],
                     'descricao': o['descricao'] or '', 'pre': o['pre_requisito'] or ''}
                    for o in sorted(options, key=lambda o: o['nome'])]
        ids = {o['id_opcao'] for o in options}
        access = [a for a in self.data['access'] if a['id_opcao_id'] in ids]
        level = int(ctx.get('nivel') or 1)
        if explicit or access or constraints.get('subclass_only'):
            allowed = {a['id_opcao_id'] for a in access
                if a['nivel_recebimento'] <= level and (
                    (not constraints.get('subclass_only') and
                     classe is not None and a['id_classe_id'] == classe) or
                    (subclasse is not None and a['id_subclasse_id'] == subclasse))}
            options = [o for o in options if o['id_opcao'] in allowed]
        return [{'id': o['id_opcao'], 'slug': o['slug'], 'nome': o['nome'],
                 'descricao': o['descricao'] or '', 'pre': o['pre_requisito'] or ''}
                for o in sorted(options, key=lambda o: o['nome'])]


    def selected_features(self, choices):
        """Resolve linked choices by identity; legacy unlinked values by exact slug.

        A missing linked identity is corruption, never permission to substitute a
        different current option. Unlinked values may belong to non-option menus.
        """
        objects = [TbOpcaojogo(**deepcopy(row)) for row in self.data['options']]
        by_id = {o.pk: o for o in objects}
        by_slug = {o.slug: o for o in objects}
        features = []
        for choice in choices:
            if choice.id_opcao_id is not None:
                if choice.id_opcao_id not in by_id:
                    raise ValueError('Selected option is absent from the pinned ruleset.')
                option = by_id[choice.id_opcao_id]
            else:
                option = by_slug.get(choice.valor)
            if option is not None and option.tags_json:
                features.append(('opcao', option.nome, option, None))
        return features
