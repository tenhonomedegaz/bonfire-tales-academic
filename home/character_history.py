"""Historico reversivel da build de personagens.

O snapshot cobre somente a estrutura mecanica da ficha. Economia, aventuras, texto
narrativo e aparencia pertencem a outros ledgers e nunca sao restaurados por aqui.
"""

from django.db.models import Max, Sum


PERSON_FIELDS = (
    'nome', 'id_raca_id', 'id_linhagem_id', 'id_essencia_id', 'id_antecedente_id',
    'forca', 'destreza', 'constituicao', 'inteligencia', 'sabedoria', 'carisma',
    'nivel', 'pv_maximo', 'pv_atual', 'pv_temporario', 'ca', 'iniciativa_bonus',
    'velocidade',
)


RELATED = (
    ('classes', 'TbPersonagemClasse', (
        'id_classe_id', 'id_subclasse_id', 'nivel', 'principal')),
    ('pericias', 'TbPersonagemPericia', (
        'nome', 'atributo', 'proficiente', 'expertise')),
    ('escolhas', 'TbPersonagemEscolha', (
        'origem', 'tipo', 'slot', 'id_opcao_id', 'valor')),
    ('magias', 'TbPersonagemMagia', (
        'id_magia_id', 'nivel', 'nome', 'preparada', 'sempre_preparada', 'origem')),
    ('talentos', 'TbPersonagemTalento', (
        'id_talento_id', 'categoria', 'nivel', 'nome', 'detalhes')),
    ('proficiencias', 'TbPersonagemProficiencia', (
        'tipo', 'nome', 'origem')),
    ('atributo_bonus', 'TbPersonagemAtributoBonus', (
        'atributo', 'valor', 'origem', 'origem_tipo')),
    ('recursos', 'TbPersonagemRecurso', (
        'nome', 'atual', 'maximo')),
)


CREATION_ITEM_FIELDS = (
    'qtd', 'nome', 'custo', 'peso', 'equipado', 'sintonizado', 'tags_json',
    'id_item_mundano_id', 'id_item_magico_id', 'origem_tipo',
)


def _models():
    from . import models
    return models


def capture_build(personagem, *, include_creation_items=False):
    """Serializa o estado mecanico atual em tipos nativos de JSON."""
    snapshot = {
        'version': 1,
        'personagem': {field: getattr(personagem, field) for field in PERSON_FIELDS},
    }
    for relation, _model_name, fields in RELATED:
        qs = getattr(personagem, relation).all()
        if relation == 'proficiencias':
            # Treinamento em jogo pertence ao painel da staff, nao a build escolhida.
            qs = qs.exclude(origem='Treinamento')
        snapshot[relation] = list(qs.order_by('pk').values(*fields))
    if include_creation_items:
        snapshot['itens_criacao'] = list(
            personagem.inventario.filter(origem_tipo='criacao')
            .order_by('pk').values(*CREATION_ITEM_FIELDS))
    return snapshot


def restore_build(personagem, snapshot):
    """Restaura um snapshot em ``personagem`` dentro da transacao do chamador."""
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1:
        raise ValueError('Snapshot de build invalido.')
    models = _models()
    person_data = snapshot.get('personagem') or {}
    for field in PERSON_FIELDS:
        if field in person_data:
            setattr(personagem, field, person_data[field])
    personagem.save(update_fields=[
        field[:-3] if field.endswith('_id') else field for field in PERSON_FIELDS
    ] + ['atualizado_em'])

    for relation, model_name, fields in RELATED:
        manager = getattr(personagem, relation)
        preserved = []
        if relation == 'proficiencias':
            preserved = list(manager.filter(origem='Treinamento'))
            manager.exclude(origem='Treinamento').delete()
        else:
            manager.all().delete()
        model = getattr(models, model_name)
        rows = []
        for raw in snapshot.get(relation) or []:
            if not isinstance(raw, dict):
                continue
            values = {field: raw.get(field) for field in fields}
            rows.append(model(id_personagem=personagem, **values))
        if rows:
            model.objects.bulk_create(rows)
        # ``preserved`` mantem referencias vivas e documenta a excecao; as linhas nunca
        # foram removidas, portanto nao precisam ser recriadas.
        del preserved

    if 'itens_criacao' in snapshot:
        personagem.inventario.filter(origem_tipo='criacao').delete()
        model = models.TbPersonagemItem
        rows = []
        for raw in snapshot.get('itens_criacao') or []:
            if not isinstance(raw, dict):
                continue
            values = {field: raw.get(field) for field in CREATION_ITEM_FIELDS}
            values['origem_tipo'] = 'criacao'
            rows.append(model(id_personagem=personagem, **values))
        if rows:
            model.objects.bulk_create(rows)
    return personagem


def adventure_marker(personagem):
    return personagem.aventuras_ledger.filter(
        revertido=False).exclude(origem='recompensa_comunidade').aggregate(
        marker=Max('id_lancamento'))['marker']


def had_adventure_after(personagem, *, marker_id=None, adventures=None, moment=None):
    """True quando existe mesa ativa posterior ao estado auditado.

    A contagem protege bancos legados sem ledger; o marcador protege a ordem normal de
    lancamentos. Uma mesa revertida deixa de bloquear a revisao.
    """
    if adventures is not None:
        community = personagem.aventuras_ledger.filter(
            revertido=False, origem='recompensa_comunidade')
        if moment is not None:
            community = community.filter(criado_em__gt=moment)
        elif marker_id is not None:
            community = community.filter(id_lancamento__gt=marker_id)
        community_after = community.aggregate(total=Sum('qtd_aventuras'))['total'] or 0
        if int(personagem.aventuras or 0) - int(adventures or 0) > community_after:
            return True
    qs = personagem.aventuras_ledger.filter(
        revertido=False).exclude(origem='recompensa_comunidade')
    if marker_id is not None:
        return qs.filter(id_lancamento__gt=marker_id).exists()
    if moment is not None:
        return qs.filter(criado_em__gt=moment).exists()
    return qs.exists()


def register_revision(personagem, *, tipo, snapshot, user=None, descricao='',
                      nivel_antes=None, nivel_depois=None):
    models = _models()
    return models.TbPersonagemRevisao.objects.create(
        id_personagem=personagem,
        tipo=tipo,
        descricao=(descricao or '')[:255],
        snapshot_json=snapshot,
        nivel_antes=int(nivel_antes if nivel_antes is not None else personagem.nivel or 1),
        nivel_depois=int(nivel_depois if nivel_depois is not None else personagem.nivel or 1),
        aventuras_no_momento=int(personagem.aventuras or 0),
        aventura_marker_id=adventure_marker(personagem),
        criado_por=user,
    )


def latest_active_revision(personagem):
    return personagem.revisoes_build.filter(revertida=False).order_by(
        '-criado_em', '-id_revisao').first()


def revision_status(personagem, revision, *, staff=False):
    if revision is None or revision.id_personagem_id != personagem.pk or revision.revertida:
        return False, 'Revisao indisponivel.'
    latest = latest_active_revision(personagem)
    if latest is None or latest.pk != revision.pk:
        return False, 'Reverta primeiro a alteracao mais recente da build.'
    if not staff and had_adventure_after(
            personagem, marker_id=revision.aventura_marker_id,
            adventures=revision.aventuras_no_momento, moment=revision.criado_em):
        return False, 'A ficha ja foi usada em uma mesa depois desta escolha.'
    return True, ''


def level_one_rebuild_status(personagem, *, staff=False):
    if staff:
        return True, ''
    if int(personagem.nivel or 1) != 1:
        return False, 'Volte os level-ups antes de recriar o nivel 1.'
    last = personagem.revisoes_build.filter(
        tipo='nivel_1', revertida=False).order_by('-criado_em', '-id_revisao').first()
    if last:
        if had_adventure_after(
                personagem, marker_id=last.aventura_marker_id,
                adventures=last.aventuras_no_momento, moment=last.criado_em):
            return False, 'A ficha ja foi usada em uma mesa depois da ultima recriacao.'
        return True, ''
    community_progress = personagem.aventuras_ledger.filter(
        revertido=False, origem='recompensa_comunidade').aggregate(
            total=Sum('qtd_aventuras'))['total'] or 0
    if ((int(personagem.aventuras or 0) - community_progress > 0) or
            personagem.aventuras_ledger.filter(
                revertido=False).exclude(origem='recompensa_comunidade').exists()):
        return False, 'O nivel 1 ja foi usado em mesa.'
    return True, ''
