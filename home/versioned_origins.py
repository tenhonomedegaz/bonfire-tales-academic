"""Sealed background and talent sources, including legacy racial talent names."""
from copy import deepcopy
from django.db import transaction
from .content_versions import create_revision, resolve_content
from .models import TbAntecedente, TbTalento, TbTracoracial, TbRaca, TbLinhagem, TbEssencia
from .versioned_classes import EVALUATOR, VOCABULARY, _fields

MODELS = (TbAntecedente, TbTalento, TbTracoracial)
RACIAL_MODELS = (TbRaca, TbLinhagem, TbEssencia)
IDENTITY = 'origin-catalog'
# Revisões seladas antes dos controles visuais de enquadramento não têm estes
# campos. O default do modelo (50) reproduz o enquadramento central antigo.
# A compatibilidade é deliberadamente restrita a metadados de apresentação.
LEGACY_VISUAL_FIELDS = {'imagem_foco_x', 'imagem_foco_y'}


@transaction.atomic
def snapshot_origins(*, author=None):
    return create_revision(IDENTITY, {'schema': 2, 'collections': {
        m._meta.label_lower: [_fields(o) for o in m.objects.order_by('pk')]
        for m in MODELS + RACIAL_MODELS}}, author=author)


class VersionedOrigins:
    def __init__(self, ruleset):
        self.data = resolve_content(ruleset, IDENTITY, evaluator_version=EVALUATOR,
                                    vocabulary_version=VOCABULARY)
        if self.data.get('schema') not in (1, 2):
            raise ValueError('Unsupported origin snapshot.')
        models = MODELS + RACIAL_MODELS if self.data['schema'] == 2 else MODELS
        for model in models:
            fields = {f.attname for f in model._meta.concrete_fields}
            allowed_missing = LEGACY_VISUAL_FIELDS if model in RACIAL_MODELS else set()
            if any((set(row) - fields) or
                   (fields - set(row)) - allowed_missing
                   for row in self.data['collections'][model._meta.label_lower]):
                raise ValueError('Incompatible origin snapshot fields.')

    def objects(self, model):
        return [model(**deepcopy(row)) for row in self.data['collections'][model._meta.label_lower]]

    def background(self, personagem):
        if not personagem.id_antecedente_id:
            return []
        obj = next((o for o in self.objects(TbAntecedente)
                    if o.pk == personagem.id_antecedente_id), None)
        if obj is None:
            raise ValueError('Background absent from pinned ruleset.')
        return [('antecedente', obj.nome, obj, None)]

    def talents(self, personagem):
        talents = {t.pk: t for t in self.objects(TbTalento)}
        traits = self.objects(TbTracoracial)
        out = []
        for selected in personagem.talentos.all():
            if selected.id_talento_id:
                if selected.id_talento_id not in talents:
                    raise ValueError('Talent absent from pinned ruleset.')
                out.append(('talento', selected.categoria or 'talento',
                            talents[selected.id_talento_id], None))
                continue
            matching = [t for t in traits if t.nome == selected.nome]
            scoped = [t for t in matching if any(
                getattr(personagem, field, None) and
                getattr(t, field) == getattr(personagem, field)
                for field in ('id_raca_id', 'id_linhagem_id', 'id_essencia_id'))]
            candidates = scoped or [t for t in matching if t.talento_racial]
            if candidates:
                tr = candidates[0]
                out.append(('talento-racial', tr.nome, tr, None))
        return out


    def racial(self, personagem):
        from .character_engine import _CLA_RE, _slug, cla_de_traco, cla_escolhido
        if self.data['schema'] < 2:
            raise ValueError('Pinned origin revision lacks racial identities.')
        if not personagem.id_raca_id:
            return []
        traits = self.objects(TbTracoracial)
        out = []
        for kind, model, field in (('raca', TbRaca, 'id_raca_id'),
                                   ('linhagem', TbLinhagem, 'id_linhagem_id'),
                                   ('essencia', TbEssencia, 'id_essencia_id')):
            identity = getattr(personagem, field, None)
            if not identity:
                continue
            parent = next((o for o in self.objects(model) if o.pk == identity), None)
            if parent is None:
                raise ValueError('Racial identity absent from pinned ruleset.')
            relevant = [t for t in traits if getattr(t, field) == identity]
            clans = {}
            if kind == 'essencia':
                for trait in relevant:
                    for match in _CLA_RE.finditer(trait.pre_requisito or ''):
                        name = match.group(1).strip()
                        slug = _slug(name)
                        if slug and slug not in clans:
                            clans[slug] = name if name[:1].isupper() else name.title()
            clan_list = [{'slug': slug, 'nome': name} for slug, name in
                         sorted(clans.items(), key=lambda pair: pair[1].lower())]
            chosen = cla_escolhido(personagem) if clans else ''
            for trait in relevant:
                if trait.talento_racial:
                    continue
                if kind == 'raca' and (trait.id_linhagem_id or trait.id_essencia_id):
                    continue
                clan = cla_de_traco(trait, clan_list) if clans else ''
                if clan and clan != chosen:
                    continue
                out.append((kind, parent.nome, trait, None))
        return out
