# -*- coding: utf-8 -*-
"""Conquistas (F3) — concessão manual/staff + recompensa que cai no inventário +
vitrine no perfil.

Fonte única de concessão: `conceder_conquista(user, conquista, por=None)`. TODO
ponto que conceda uma conquista (admin action, futura automática) DEVE passar por
aqui — assim a recompensa sempre é materializada no inventário de cosméticos e a
operação é idempotente.

Vitrine: helpers que montam o estado das conquistas de um usuário pro perfil
público (compacto) e pro editor do próprio usuário. Secretas NUNCA aparecem pra
quem não as tem (não vaza existência). Batch pra /jogadores/ sem N+1.

Ver docs/agentes/arquitetura_personalizacao_perfil.md §3 e §7 (F3).
"""

from django.db import transaction


def regra_unidades_compradas_valida(regra):
    """Aceita apenas identidades estruturadas e comparadores configuráveis seguros."""
    if not isinstance(regra, dict) or set(regra) != {
            'schema_version', 'metric', 'scope', 'aggregate', 'filters', 'operator', 'target'}:
        return False
    if (type(regra['schema_version']) is not int or regra['schema_version'] != 1 or
            regra['metric'] != 'items_purchased_units' or
            regra['scope'] != 'account' or regra['aggregate'] != 'sum' or
            type(regra['operator']) is not str or regra['operator'] not in {'gt', 'gte'} or
            type(regra['target']) is not int or regra['target'] <= 0):
        return False
    filters = regra['filters']
    if not isinstance(filters, dict) or set(filters) != {'items'}:
        return False
    items = filters['items']
    if not isinstance(items, list) or not items or len(items) > 100:
        return False
    identities = []
    for item in items:
        if (not isinstance(item, dict) or set(item) != {'catalog', 'id'} or
                type(item['catalog']) is not str or
                item['catalog'] not in {'mundano', 'magico', 'oficina', 'comunidade'} or
                type(item['id']) is not int or item['id'] <= 0):
            return False
        identities.append((item['catalog'], item['id']))
    return len(set(identities)) == len(identities)


def identidades_itens_ausentes(items):
    """Confere IDs usados no payload de compras dos quatro catálogos do site."""
    from .models import TbAnuncioItemMagico, TbItemMagico, TbItemMundano, TbMagia

    catalogos = {
        'mundano': TbItemMundano,
        'magico': TbItemMagico,
        'oficina': TbMagia,
        'comunidade': TbAnuncioItemMagico,
    }
    missing = []
    for catalog, model in catalogos.items():
        ids = {item['id'] for item in items if item['catalog'] == catalog}
        if ids:
            found = set(model.objects.filter(pk__in=ids).values_list('pk', flat=True))
            missing.extend(f'{catalog}:{item_id}' for item_id in sorted(ids - found))
    return missing


def regra_inicio_classe_valida(regra):
    """Uma classe inicial é identificada por slug de catálogo, nunca por nome."""
    import re

    return (isinstance(regra, dict) and set(regra) == {
        'schema_version', 'metric', 'scope', 'filters', 'operator', 'target'} and
        type(regra['schema_version']) is int and regra['schema_version'] == 1 and
        regra['metric'] == 'class_started' and regra['scope'] == 'account' and
        regra['operator'] == 'gte' and type(regra['target']) is int and
        regra['target'] == 1 and isinstance(regra['filters'], dict) and
        set(regra['filters']) == {'class_slug'} and
        type(regra['filters']['class_slug']) is str and
        bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',
                          regra['filters']['class_slug'])))


def regra_aventuras_jogadas_valida(regra):
    """Soma apenas mesas comprovadas no ledger do site; limiar vem do cadastro."""
    return (isinstance(regra, dict) and set(regra) == {
        'schema_version', 'metric', 'scope', 'aggregate', 'filters', 'operator', 'target'} and
        type(regra['schema_version']) is int and regra['schema_version'] == 1 and
        regra['metric'] == 'adventures_played' and regra['scope'] == 'account' and
        regra['aggregate'] == 'sum' and regra['filters'] == {
            'valid': True, 'origin': 'played_session'} and
        type(regra['operator']) is str and regra['operator'] in {'gt', 'gte'} and
        type(regra['target']) is int and regra['target'] > 0)


QUEST_CATEGORIES = {
    'bg_token': 'BG/token',
    'item_rare': 'Item raro',
    'item_very_rare': 'Item muito raro',
    'item_legendary': 'Item lendário',
}


def regra_quest_categorizada_valida(regra):
    return (isinstance(regra, dict) and set(regra) == {
        'schema_version', 'metric', 'scope', 'filters', 'operator', 'target'} and
        type(regra['schema_version']) is int and regra['schema_version'] == 1 and
        regra['metric'] == 'quests_completed' and regra['scope'] == 'account' and
        isinstance(regra['filters'], dict) and
        set(regra['filters']) == {'category', 'valid'} and
        regra['filters']['valid'] is True and
        type(regra['filters']['category']) is str and
        regra['filters']['category'] in QUEST_CATEGORIES and
        regra['operator'] == 'gte' and type(regra['target']) is int and
        regra['target'] == 1)


def regra_nivel_personagem_valida(regra):
    """Marco de nível atual por classe principal, com limiar editorial explícito."""
    import re

    return (isinstance(regra, dict) and set(regra) == {
        'schema_version', 'metric', 'scope', 'filters', 'operator', 'target'} and
        type(regra['schema_version']) is int and regra['schema_version'] == 1 and
        regra['metric'] == 'character_level' and regra['scope'] == 'account' and
        regra['operator'] == 'gte' and type(regra['target']) is int and
        2 <= regra['target'] <= 20 and isinstance(regra['filters'], dict) and
        set(regra['filters']) in ({'class_slug'}, {'class_slug', 'single_class'}) and
        type(regra['filters']['class_slug']) is str and
        (('single_class' not in regra['filters']) or
         (regra['filters']['single_class'] is True and regra['target'] == 20)) and
        bool(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',
                          regra['filters']['class_slug'])))


def ranks_verificaveis():
    """Faixas publicadas de 5 a 20; as patentes épicas aguardam mapeamento do PO."""
    from .character_engine import rank_por_nivel

    thresholds = {}
    for level in range(5, 21):
        thresholds.setdefault(rank_por_nivel(level), level)
    return thresholds


def regra_rank_valida(regra):
    return (isinstance(regra, dict) and set(regra) == {
        'schema_version', 'metric', 'scope', 'filters', 'operator', 'target'} and
        type(regra['schema_version']) is int and regra['schema_version'] == 1 and
        regra['metric'] == 'rank_reached' and regra['scope'] == 'account' and
        isinstance(regra['filters'], dict) and set(regra['filters']) == {'rank'} and
        type(regra['filters']['rank']) is str and
        regra['filters']['rank'] in ranks_verificaveis() and
        regra['operator'] == 'gte' and type(regra['target']) is int and
        regra['target'] == 1)


def recompensa_ids_da_conquista(conquista):
    """Une o prêmio legado aos adicionais sem conceder o mesmo item duas vezes."""
    ids = set(conquista.recompensas_extras.values_list('pk', flat=True))
    if conquista.recompensa_id:
        ids.add(conquista.recompensa_id)
    return ids


def _suspender_recompensas_sem_direito(grant, now):
    """Retira somente itens cuja última fonte ativa era esta conquista."""
    from django.db.models import Q
    from .models import (CosmeticCheckoutPurchase, TbUsuarioConquista,
                         TbUsuarioCosmetico)

    for reward_id in recompensa_ids_da_conquista(grant.conquista):
        another_grant = TbUsuarioConquista.objects.filter(
            user_id=grant.user_id, revogada_em__isnull=True,
        ).filter(Q(conquista__recompensa_id=reward_id) |
                 Q(conquista__recompensas_extras__pk=reward_id)).exclude(
                     pk=grant.pk).exists()
        purchased = CosmeticCheckoutPurchase.objects.filter(
            beneficiary_id=grant.user_id, cosmetico_id=reward_id,
            granted_at__isnull=False).exists()
        if not another_grant and not purchased:
            TbUsuarioCosmetico.objects.filter(
                user_id=grant.user_id, cosmetico_id=reward_id,
                origem__startswith='conquista:', suspenso_em__isnull=True,
            ).update(suspenso_em=now)


@transaction.atomic
def conceder_conquista(user, conquista, por=None):
    """Concede `conquista` a `user` (idempotente). Se ainda não tinha, cria a
    linha TbUsuarioConquista e, havendo recompensa, desbloqueia o cosmético no
    inventário (get_or_create em TbUsuarioCosmetico com origem 'conquista:<slug>').

    Retorna (criada: bool) — True se foi a primeira concessão, False se já tinha.
    Mesmo quando já tinha, garante que a recompensa esteja no inventário (auto-cura
    casos em que a recompensa foi ligada depois da concessão). Concessão e recompensa
    são persistidas juntas, inclusive em chamadas diretas da staff."""
    if not user or not getattr(user, 'pk', None) or conquista is None:
        return False
    from .models import (TbConquistaNotificacao, TbCosmetico, TbUsuarioConquista,
                         TbUsuarioCosmetico)

    reward_ids = recompensa_ids_da_conquista(conquista)
    if TbCosmetico.objects.filter(pk__in=reward_ids, tipo='moldura', animado=True).exists():
        raise ValueError('Molduras animadas são exclusivas de compra ou Colab.')

    concessao, criada = TbUsuarioConquista.objects.get_or_create(
        user=user, conquista=conquista,
        defaults={'concedida_por': por if getattr(por, 'pk', None) else None},
    )
    if concessao.revogada_em is not None:
        concessao.revogada_em = None
        concessao.save(update_fields=['revogada_em'])
        criada = True
    if getattr(por, 'pk', None) and concessao.concedida_por_id is None:
        concessao.concedida_por = por
        concessao.save(update_fields=['concedida_por'])
    # Materializa a recompensa no inventário (idempotente por unique_together
    # user+cosmetico). Roda mesmo em re-concessão pra cobrir recompensa adicionada
    # depois — nunca duplica.
    for reward_id in reward_ids:
        posse, _ = TbUsuarioCosmetico.objects.get_or_create(
            user=user, cosmetico_id=reward_id,
            defaults={'origem': 'conquista:%s' % conquista.slug},
        )
        if posse.suspenso_em:
            posse.suspenso_em = None
            posse.origem = 'conquista:%s' % conquista.slug
            posse.save(update_fields=['suspenso_em', 'origem'])
    if criada:
        aviso, novo = TbConquistaNotificacao.objects.get_or_create(concessao=concessao)
        if not novo:
            from django.utils import timezone
            aviso.lida_em = None
            aviso.criada_em = timezone.now()
            aviso.save(update_fields=['lida_em', 'criada_em'])
    return criada


@transaction.atomic
def conceder_conquista_em_massa(users, conquista, por=None):
    """Concede `conquista` a vários usuários. Retorna (concedidas, ja_tinham).
    Usa `conceder_conquista` por usuário (fonte única)."""
    concedidas = ja_tinham = 0
    for u in users:
        if conceder_conquista(u, conquista, por=por):
            concedidas += 1
        else:
            ja_tinham += 1
    return concedidas, ja_tinham


@transaction.atomic
def revogar_conquista_manual(concessao):
    """Revoga concessão da staff, inclusive exceção manual de regra automática.

    Concessões automáticas sem concedente pertencem ao avaliador de fatos.
    """
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbUsuarioConquista,
                         TbUsuarioCosmetico)

    grant = (TbUsuarioConquista.objects.select_for_update()
             .select_related('conquista').get(pk=concessao.pk))
    if ((grant.conquista.criterio != 'manual' and grant.concedida_por_id is None) or
            grant.revogada_em is not None):
        return False
    now = timezone.now()
    grant.revogada_em = now
    grant.save(update_fields=['revogada_em'])
    _suspender_recompensas_sem_direito(grant, now)
    return True


def registrar_criacao_personagem(personagem):
    """Registra a criação confirmada e concede a métrica da primeira ficha.

    Chamado somente pelo endpoint de criação real, dentro da mesma transação da
    ficha. Prévia e recriação de nível 1 usam o persistidor, mas não este serviço.
    """
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from .models import TbEventoConquista, TbPersonagem, TbPersonagemClasse
    with transaction.atomic():
        # Duas criações simultâneas da mesma conta devem avaliar "primeira" em série.
        get_user_model().objects.select_for_update().only('pk').get(pk=personagem.dono_id)
        principal = TbPersonagemClasse.objects.filter(
            id_personagem=personagem, principal=True, nivel=1
        ).select_related('id_classe').first() if personagem.nivel == 1 else None
        chave_criacao = f'personagem:{personagem.pk}:criado'
        primeira_ficha = (
            not TbPersonagem.objects.filter(
                dono_id=personagem.dono_id).exclude(pk=personagem.pk).exists() and
            not TbEventoConquista.objects.filter(
                conta_id=personagem.dono_id, origem='site',
                tipo='character_created').exclude(chave_origem=chave_criacao).exists()
        )
        class_snapshot = ({'initial_class_id': principal.id_classe_id,
                           'initial_class_slug': principal.id_classe.slug,
                           'initial_level': 1} if principal else {})
        evento, _ = TbEventoConquista.objects.get_or_create(
            origem='site', chave_origem=chave_criacao,
            defaults={
                'tipo': 'character_created', 'conta_id': personagem.dono_id,
                'personagem': personagem, 'agregado_id': personagem.pk,
                'ocorrido_em': personagem.criado_em,
                'payload_json': {**class_snapshot, 'first_character': primeira_ficha},
            },
        )
        if evento.conta_id != personagem.dono_id or evento.agregado_id != personagem.pk:
            raise ValueError('Identidade do fato de criação inconsistente.')
        avaliar_inicio_classe_evento(evento)
        avaliar_primeira_ficha_evento(evento)
    return evento


def registrar_fato_level_up(revisao, *, estorno=False, proxima_revisao=None):
    """Registra a revisão e atualiza marcos de nível na mesma transação."""
    from .models import TbEventoConquista

    if revisao.tipo != 'level_up' or revisao.nivel_depois <= revisao.nivel_antes:
        return None
    personagem = revisao.id_personagem
    key = f'personagem:{personagem.pk}:revisao:{revisao.pk}:level_up'
    if estorno:
        if not revisao.revertida or not revisao.revertida_em:
            raise ValueError('A revisão ainda não foi revertida.')
        tipo, key, occurred = 'character_level_reverted', key + ':revertido', revisao.revertida_em
        payload = {'revision_id': revisao.pk, 'level_before': revisao.nivel_depois,
                   'level_after': revisao.nivel_antes}
    else:
        tipo, occurred = 'character_level_up', revisao.criado_em
        previous_event = TbEventoConquista.objects.filter(
            origem='site', chave_origem=key).first()
        if previous_event:
            # O estado atual pode estar em outro nível; o fato original é imutável.
            payload = previous_event.payload_json or {}
        else:
            snapshot = revisao.snapshot_json or {}
            if not isinstance(snapshot, dict):
                raise ValueError('Snapshot anterior inválido.')
            before = snapshot.get('personagem') or {}
            classes_before = snapshot.get('classes') or []
            if (not isinstance(before, dict) or
                    type(before.get('nivel')) is not int or
                    not isinstance(classes_before, list) or not classes_before or
                    any(not isinstance(row, dict) or
                        type(row.get('id_classe_id')) is not int or
                        type(row.get('nivel')) is not int or row['nivel'] <= 0 or
                        type(row.get('principal')) is not bool
                        for row in classes_before) or
                    sum(row['principal'] for row in classes_before) != 1):
                raise ValueError('Snapshot anterior sem classes comprováveis.')
            if proxima_revisao is None:
                classes_after = list(personagem.classes.order_by('pk').values(
                    'id_classe_id', 'nivel', 'principal'))
                after_level = personagem.nivel
            else:
                from .models import TbPersonagemRevisao
                next_snapshot = proxima_revisao.snapshot_json
                if (proxima_revisao.id_personagem_id != personagem.pk or
                        proxima_revisao.pk <= revisao.pk or
                        TbPersonagemRevisao.objects.filter(
                            id_personagem=personagem, pk__gt=revisao.pk,
                            pk__lt=proxima_revisao.pk).exists() or
                        proxima_revisao.nivel_antes != revisao.nivel_depois or
                        not isinstance(next_snapshot, dict)):
                    raise ValueError('Revisão posterior não comprova a trajetória.')
                after = next_snapshot.get('personagem')
                classes_after = next_snapshot.get('classes')
                after_level = after.get('nivel') if isinstance(after, dict) else None
                if (not isinstance(classes_after, list) or not classes_after or
                        any(not isinstance(row, dict) or
                            type(row.get('id_classe_id')) is not int or
                            type(row.get('nivel')) is not int or row['nivel'] <= 0 or
                            type(row.get('principal')) is not bool
                            for row in classes_after) or
                        sum(row['principal'] for row in classes_after) != 1):
                    raise ValueError('Snapshot posterior sem classes comprováveis.')
            if (before.get('nivel') != revisao.nivel_antes or
                    after_level != revisao.nivel_depois or
                    sum(row['nivel'] for row in classes_before) != revisao.nivel_antes or
                    sum(row['nivel'] for row in classes_after) != revisao.nivel_depois):
                raise ValueError('Trajetória de nível inconsistente com a revisão.')
            payload = {'revision_id': revisao.pk, 'level_before': revisao.nivel_antes,
                       'level_after': revisao.nivel_depois,
                       'classes_before': classes_before, 'classes_after': classes_after}
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site', chave_origem=key,
        defaults={'tipo': tipo, 'conta_id': personagem.dono_id,
                  'personagem': personagem, 'agregado_id': revisao.pk,
                  'ocorrido_em': occurred, 'payload_json': payload},
    )
    if (evento.tipo != tipo or evento.conta_id != personagem.dono_id or
            evento.personagem_id != personagem.pk or
            evento.agregado_id != revisao.pk or evento.payload_json != payload or
            evento.ocorrido_em != occurred or evento.versao_payload != 1 or
            payload.get('revision_id') != revisao.pk or
            payload.get('level_before') != (revisao.nivel_depois if estorno else revisao.nivel_antes) or
            payload.get('level_after') != (revisao.nivel_antes if estorno else revisao.nivel_depois)):
        raise ValueError('Identidade do fato de nível inconsistente.')
    avaliar_nivel_personagem(personagem.dono)
    return evento


def _historico_classe_unica(character, class_id):
    """Confere origem, snapshots e fatos de level-up da classe única."""
    from .models import TbEventoConquista, TbPersonagemRevisao

    creation = TbEventoConquista.objects.filter(
        origem='site', tipo='character_created', conta_id=character.dono_id,
        personagem=character, agregado_id=character.pk,
        chave_origem=f'personagem:{character.pk}:criado',
    ).first()
    origin = creation.payload_json if creation else None
    if (creation is None or creation.versao_payload != 1 or
            not isinstance(origin, dict) or origin.get('initial_class_id') != class_id or
            origin.get('initial_level') != 1):
        return False
    revisions = list(TbPersonagemRevisao.objects.filter(
        id_personagem=character).only('snapshot_json', 'nivel_antes', 'nivel_depois',
                                     'tipo', 'revertida', 'criado_em'))
    if not revisions:
        return False
    level_revisions = sorted(
        (revision for revision in revisions
         if revision.tipo == 'level_up' and not revision.revertida),
        key=lambda revision: (revision.criado_em, revision.pk))
    expected_level = 1
    for revision in level_revisions:
        if (revision.nivel_antes != expected_level or
                revision.nivel_depois != expected_level + 1):
            return False
        expected_level = revision.nivel_depois
    if expected_level != character.nivel:
        return False
    events = {event.agregado_id: event for event in TbEventoConquista.objects.filter(
        origem='site', tipo='character_level_up', conta_id=character.dono_id,
        personagem=character,
        agregado_id__in=[revision.pk for revision in level_revisions])}
    for revision in revisions:
        snapshot = revision.snapshot_json
        if not isinstance(snapshot, dict):
            return False
        classes = snapshot.get('classes')
        before = snapshot.get('personagem')
        if (not isinstance(classes, list) or len(classes) != 1 or
                not isinstance(classes[0], dict) or
                classes[0].get('id_classe_id') != class_id or
                classes[0].get('principal') is not True or
                not isinstance(before, dict) or
                before.get('nivel') != revision.nivel_antes or
                classes[0].get('nivel') != revision.nivel_antes):
            return False
    for revision in level_revisions:
        event = events.get(revision.pk)
        if (event is None or event.versao_payload != 1 or event.chave_origem !=
                f'personagem:{character.pk}:revisao:{revision.pk}:level_up'):
            return False
        payload = event.payload_json or {}
        after = payload.get('classes_after')
        if (payload.get('revision_id') != revision.pk or
                payload.get('level_before') != revision.nivel_antes or
                payload.get('level_after') != revision.nivel_depois or
                not isinstance(after, list) or len(after) != 1 or
                not isinstance(after[0], dict) or
                after[0].get('id_classe_id') != class_id or
                after[0].get('principal') is not True or
                after[0].get('nivel') != revision.nivel_depois):
            return False
    return True


def _niveis_comprovados(user, *, single_class=False):
    """Retorna o maior nível atual por classe principal com revisão canônica válida."""
    from .models import TbEventoConquista, TbPersonagem, TbPersonagemRevisao

    levels = {}
    for character in TbPersonagem.objects.filter(dono=user).prefetch_related(
            'classes__id_classe'):
        primary = [row for row in character.classes.all() if row.principal]
        if len(primary) != 1 or not 2 <= character.nivel <= 20:
            continue
        revision = TbPersonagemRevisao.objects.filter(
            id_personagem=character, tipo='level_up', revertida=False,
            nivel_depois=character.nivel).order_by('-criado_em', '-pk').first()
        if revision is None:
            continue
        event = TbEventoConquista.objects.filter(
            origem='site', tipo='character_level_up', conta=user,
            agregado_id=revision.pk, personagem=character,
            chave_origem=f'personagem:{character.pk}:revisao:{revision.pk}:level_up',
        ).first()
        current_classes = list(character.classes.order_by('pk').values(
            'id_classe_id', 'nivel', 'principal'))
        if (event is None or (event.payload_json or {}).get('revision_id') != revision.pk or
                (event.payload_json or {}).get('level_after') != character.nivel or
                (event.payload_json or {}).get('classes_after') != current_classes or
                sum(row['nivel'] for row in current_classes) != character.nivel):
            continue
        if single_class and (len(current_classes) != 1 or
                             not _historico_classe_unica(character, primary[0].id_classe_id)):
            continue
        slug = primary[0].id_classe.slug
        if character.nivel > levels.get(slug, (0, None))[0]:
            levels[slug] = (character.nivel, event)
    return levels


def _marcos_rank_comprovados(user):
    """Level-ups históricos íntegros; reset não apaga um marco, estorno apaga."""
    from .models import TbEventoConquista, TbPersonagemRevisao

    events = list(TbEventoConquista.objects.filter(
        origem='site', tipo='character_level_up', conta=user,
    ).select_related('personagem'))
    revisions = {row.pk: row for row in TbPersonagemRevisao.objects.filter(
        pk__in=[event.agregado_id for event in events], tipo='level_up',
        revertida=False).select_related('id_personagem')}
    supported = []
    for event in events:
        revision = revisions.get(event.agregado_id)
        payload = event.payload_json
        snapshot = revision.snapshot_json if revision else None
        before = snapshot.get('personagem') if isinstance(snapshot, dict) else None
        classes_before = snapshot.get('classes') if isinstance(snapshot, dict) else None
        if (revision is None or event.personagem_id is None or
                revision.id_personagem_id != event.personagem_id or
                event.personagem.dono_id != user.pk or event.versao_payload != 1 or
                event.chave_origem != f'personagem:{event.personagem_id}:revisao:{revision.pk}:level_up' or
                not isinstance(payload, dict) or not isinstance(before, dict) or
                not isinstance(classes_before, list) or
                payload.get('revision_id') != revision.pk or
                payload.get('level_before') != revision.nivel_antes or
                payload.get('level_after') != revision.nivel_depois or
                payload.get('classes_before') != classes_before or
                before.get('nivel') != revision.nivel_antes or
                sum(row.get('principal') is True for row in classes_before
                    if isinstance(row, dict)) != 1 or
                any(not isinstance(row, dict) or type(row.get('nivel')) is not int or
                    row['nivel'] <= 0 for row in classes_before) or
                sum(row['nivel'] for row in classes_before) != revision.nivel_antes or
                not 5 <= revision.nivel_depois <= 20 or
                revision.nivel_depois <= revision.nivel_antes):
            continue
        classes_after = payload.get('classes_after')
        if (not isinstance(classes_after, list) or
                sum(row.get('principal') is True for row in classes_after
                    if isinstance(row, dict)) != 1 or
                any(not isinstance(row, dict) or type(row.get('nivel')) is not int or
                    row['nivel'] <= 0 for row in classes_after) or
                sum(row['nivel'] for row in classes_after) != revision.nivel_depois):
            continue
        supported.append((revision.nivel_depois, event))
    return sorted(supported, key=lambda row: (row[0], row[1].pk), reverse=True)


@transaction.atomic
def avaliar_nivel_personagem(user):
    """Concede ou revoga marcos automáticos após subir ou reverter nível."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbConquista, TbUsuarioConquista,
                         TbUsuarioCosmetico)

    get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
    candidates = TbConquista.objects.filter(
        ativo=True, criterio='automatico',
        criterio_json__metric__in=['character_level', 'rank_reached'],
    ).select_related('recompensa')
    rules = [rule for rule in candidates if regra_nivel_personagem_valida(rule.criterio_json)]
    rank_rules = [rule for rule in candidates if regra_rank_valida(rule.criterio_json)]
    if not rules and not rank_rules:
        return
    levels = _niveis_comprovados(user) if rules else {}
    single_class_levels = (_niveis_comprovados(user, single_class=True)
                           if any(rule.criterio_json['filters'].get('single_class')
                                  for rule in rules) else {})
    for rule in rules:
        definition = rule.criterio_json
        proof = (single_class_levels if definition['filters'].get('single_class')
                 else levels)
        level, event = proof.get(definition['filters']['class_slug'], (0, None))
        grant = TbUsuarioConquista.objects.select_for_update().filter(
            user=user, conquista=rule).first()
        if level >= definition['target']:
            if grant is None or grant.concedida_por_id is None:
                conceder_conquista(user, rule)
                TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                    evidencia_json={'evento_id': str(event.pk),
                                   'chave_origem': event.chave_origem,
                                   'agregado_id': event.agregado_id,
                                   'personagem_id': event.personagem_id,
                                   'nivel': level},
                    definicao_json=definition)
        elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
            now = timezone.now()
            grant.revogada_em = now
            grant.save(update_fields=['revogada_em'])
            _suspender_recompensas_sem_direito(grant, now)
    if rank_rules:
        rank_sources = _marcos_rank_comprovados(user)
        thresholds = ranks_verificaveis()
        for rule in rank_rules:
            threshold = thresholds[rule.criterio_json['filters']['rank']]
            qualifying = [(level, event) for level, event in rank_sources
                          if level >= threshold]
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if qualifying:
                if grant is None or grant.concedida_por_id is None:
                    conceder_conquista(user, rule)
                    level, event = qualifying[0]
                    TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                        evidencia_json={'evento_id': str(event.pk),
                                        'personagem_id': event.personagem_id,
                                        'personagem_ids': sorted({source.personagem_id
                                                                 for _, source in qualifying}),
                                        'nivel': level,
                                        'rank': rule.criterio_json['filters']['rank']},
                        definicao_json=rule.criterio_json)
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                _suspender_recompensas_sem_direito(grant, now)


def avaliar_primeira_ficha_evento(evento):
    """Concede a primeira ficha somente quando o fato gravou essa condição na criação.

    Fatos antigos sem a prova explícita não são inferidos de fichas ainda existentes:
    uma exclusão ou reset poderia transformar uma segunda ficha em falsa primeira.
    """
    from .models import TbConquista, TbUsuarioConquista

    if (evento.origem != 'site' or evento.tipo != 'character_created' or
            evento.chave_origem != f'personagem:{evento.agregado_id}:criado' or
            evento.personagem_id not in (None, evento.agregado_id) or
            (evento.payload_json or {}).get('first_character') is not True):
        return 0
    regra = {'schema_version': 1, 'metric': 'characters_created',
             'scope': 'account', 'operator': 'gte', 'target': 1}
    awarded = 0
    for conquista in TbConquista.objects.filter(
            ativo=True, criterio='automatico',
            criterio_json__metric='characters_created').select_related('recompensa'):
        if conquista.criterio_json != regra:
            continue
        grant = TbUsuarioConquista.objects.filter(
            user_id=evento.conta_id, conquista=conquista).first()
        if grant is not None and (grant.revogada_em is None or grant.concedida_por_id):
            continue
        if conceder_conquista(evento.conta, conquista):
            TbUsuarioConquista.objects.filter(
                user_id=evento.conta_id, conquista=conquista).update(
                evidencia_json={'evento_id': str(evento.pk), 'origem': evento.origem,
                               'chave_origem': evento.chave_origem,
                               'agregado_id': evento.agregado_id},
                definicao_json=regra,
            )
            awarded += 1
    return awarded


@transaction.atomic
def avaliar_inicio_classe_evento(evento):
    """Concede uma vez a classe inicial comprovada no fato imutável de criação."""
    from .models import TbConquista, TbUsuarioConquista

    if (evento.origem != 'site' or evento.tipo != 'character_created' or
            evento.chave_origem != f'personagem:{evento.agregado_id}:criado' or
            evento.personagem_id not in (None, evento.agregado_id) or
            type(evento.agregado_id) is not int or evento.agregado_id <= 0):
        return 0
    snapshot = evento.payload_json or {}
    if (type(snapshot.get('initial_class_id')) is not int or
            snapshot['initial_class_id'] <= 0 or
            type(snapshot.get('initial_class_slug')) is not str or
            snapshot.get('initial_level') != 1):
        return 0
    awarded = 0
    for rule in TbConquista.objects.filter(
            ativo=True, criterio='automatico',
            criterio_json__metric='class_started').select_related('recompensa'):
        definition = rule.criterio_json
        if (not regra_inicio_classe_valida(definition) or
                definition['filters']['class_slug'] != snapshot['initial_class_slug']):
            continue
        grant = TbUsuarioConquista.objects.select_for_update().filter(
            user_id=evento.conta_id, conquista=rule).first()
        if grant is not None and grant.concedida_por_id:
            continue
        if grant is not None and grant.revogada_em is None:
            evidence = grant.evidencia_json
            if not isinstance(evidence, dict):
                continue
            sources = evidence.get('personagem_ids')
            if not isinstance(sources, list):
                sources = [evidence.get('agregado_id')]
            sources = {source for source in sources
                       if type(source) is int and source > 0}
            if evento.agregado_id not in sources:
                grant.evidencia_json = {**evidence,
                                        'personagem_ids': sorted(sources | {evento.agregado_id})}
                grant.save(update_fields=['evidencia_json'])
            continue
        if conceder_conquista(evento.conta, rule):
            TbUsuarioConquista.objects.filter(user_id=evento.conta_id, conquista=rule).update(
                evidencia_json={'evento_id': str(evento.pk),
                                'chave_origem': evento.chave_origem,
                                'agregado_id': evento.agregado_id,
                                'initial_class_id': snapshot['initial_class_id'],
                                'initial_class_slug': snapshot['initial_class_slug']},
                definicao_json=definition)
            awarded += 1
    return awarded


def registrar_publicacao_cronica(cronica):
    """Registra a primeira publicação aprovada, sem contar revisões editoriais."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.db.models import Q
    from .models import TbConquista, TbCronica, TbEventoConquista, TbUsuarioConquista

    if cronica.status != 'aprovada' or not cronica.data_publicacao:
        raise ValueError('A crônica ainda não foi publicada.')
    regra = {
        'schema_version': 1, 'metric': 'stories_published',
        'scope': 'account', 'operator': 'gte', 'target': 1,
    }
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=cronica.autor_id)
        evento, _ = TbEventoConquista.objects.get_or_create(
            origem='site', chave_origem=f'cronica:{cronica.pk}:publicada',
            defaults={
                'tipo': 'story_published', 'conta_id': cronica.autor_id,
                'agregado_id': cronica.pk, 'ocorrido_em': cronica.data_publicacao,
            },
        )
        if (evento.tipo != 'story_published' or evento.conta_id != cronica.autor_id or
                evento.agregado_id != cronica.pk or evento.versao_payload != 1 or
                evento.ocorrido_em != cronica.data_publicacao):
            raise ValueError('Identidade do fato de publicação inconsistente.')
        anteriores = TbCronica.objects.filter(autor_id=cronica.autor_id).exclude(pk=cronica.pk)
        if anteriores.filter(
                Q(data_publicacao__lt=cronica.data_publicacao) |
                Q(data_publicacao=cronica.data_publicacao, pk__lt=cronica.pk) |
                Q(data_publicacao__isnull=True, status__in=['aprovada', 'oculta'])
        ).exists():
            return evento
        for conquista in TbConquista.objects.filter(
                ativo=True, criterio='automatico',
                criterio_json__metric='stories_published').select_related('recompensa'):
            if conquista.criterio_json != regra:
                continue
            if conceder_conquista(cronica.autor, conquista):
                TbUsuarioConquista.objects.filter(user_id=cronica.autor_id, conquista=conquista).update(
                    evidencia_json={'evento_id': str(evento.pk), 'origem': evento.origem,
                                   'chave_origem': evento.chave_origem, 'agregado_id': cronica.pk},
                    definicao_json=regra,
                )
    return evento


@transaction.atomic
def registrar_fato_aventura(lancamento, *, estorno=False, avaliar=True):
    """Persiste o fato do ledger do site, sem somá-lo a fatos ainda não vinculados do bot."""
    from .models import TbEventoConquista

    if lancamento.origem == 'recompensa_comunidade':
        raise ValueError('Recompensa comunitária não é mesa jogada.')

    if estorno:
        if not lancamento.revertido or not lancamento.revertido_em:
            raise ValueError('O lançamento ainda não foi estornado.')
        tipo, sufixo, ocorrido = 'adventure_reverted', 'revertida', lancamento.revertido_em
    else:
        if lancamento.revertido or int(lancamento.qtd_aventuras or 0) <= 0:
            raise ValueError('O lançamento não está válido.')
        tipo, sufixo, ocorrido = 'adventure_recorded', 'registrada', lancamento.criado_em
    personagem = lancamento.id_personagem
    payload = {
        'ledger_id': lancamento.pk,
        'quantidade': int(lancamento.qtd_aventuras),
        'mestre_id': lancamento.id_mestre_id,
        'data_missao': lancamento.data_missao.isoformat() if lancamento.data_missao else None,
    }
    bot_quest_id = (lancamento.detalhes_json or {}).get('bot_quest_id')
    category = (lancamento.detalhes_json or {}).get('quest_category')
    if category:
        payload['quest_category'] = category
        payload['quest_confirmed_by'] = (lancamento.detalhes_json or {}).get('quest_confirmed_by')
    if bot_quest_id:
        payload['bot_quest_id'] = bot_quest_id
        bot_prova = (lancamento.detalhes_json or {}).get('bot_quest_proof')
        if bot_prova:
            payload['bot_quest_proof'] = bot_prova
    chave = f'aventura-ledger:{lancamento.pk}:{sufixo}'
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_ledger', chave_origem=chave,
        defaults={
            'tipo': tipo, 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': lancamento.pk,
            'ocorrido_em': ocorrido, 'payload_json': payload,
        },
    )
    recorded_payload = evento.payload_json if isinstance(evento.payload_json, dict) else {}
    if (evento.tipo != tipo or evento.versao_payload != 1 or
            evento.conta_id != personagem.dono_id or
            evento.personagem_id != personagem.pk or
            evento.agregado_id != lancamento.pk or
            type(recorded_payload.get('ledger_id')) is not int or
            recorded_payload['ledger_id'] != lancamento.pk or
            type(recorded_payload.get('quantidade')) is not int or
            recorded_payload['quantidade'] != payload['quantidade'] or
            recorded_payload.get('quest_category') != payload.get('quest_category')):
        raise ValueError('Identidade do fato de aventura inconsistente.')
    if avaliar:
        avaliar_aventuras_jogadas(personagem.dono)
        avaliar_quests_categorizadas(personagem.dono)
    return evento


def _quests_comprovadas(user):
    """Categorias sustentadas por fato, ledger de mesa e confirmação da staff."""
    from .models import TbPersonagemAventura

    _, facts = _aventuras_comprovadas(user)
    ledgers = {row.pk: row for row in TbPersonagemAventura.objects.filter(
        pk__in=[fact.agregado_id for fact in facts], id_personagem__dono=user,
        origem='mesa', revertido=False).select_related('criado_por')}
    matched = {category: [] for category in QUEST_CATEGORIES}
    for fact in facts:
        ledger = ledgers.get(fact.agregado_id)
        details = ledger.detalhes_json if ledger and isinstance(ledger.detalhes_json, dict) else {}
        category = fact.payload_json.get('quest_category')
        if (category not in matched or not ledger or
                not ledger.data_missao or not ledger.id_mestre_id or
                not ledger.criado_por_id or not ledger.criado_por.is_staff or
                details.get('quest_category') != category or
                details.get('quest_confirmed_by') != ledger.criado_por_id or
                fact.payload_json.get('quest_confirmed_by') != ledger.criado_por_id):
            continue
        matched[category].append(fact)
    return matched


def avaliar_quests_categorizadas(user):
    """Concede somente categorias confirmadas pela staff em um lançamento válido."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbConquista,
                         TbUsuarioConquista, TbUsuarioCosmetico)

    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        rules = [rule for rule in TbConquista.objects.filter(
            ativo=True, criterio='automatico',
            criterio_json__metric='quests_completed').select_related('recompensa')
            if regra_quest_categorizada_valida(rule.criterio_json)]
        if not rules:
            return
        matched = _quests_comprovadas(user)
        for rule in rules:
            category = rule.criterio_json['filters']['category']
            first = matched[category][0] if matched[category] else None
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if first:
                if grant is None or grant.concedida_por_id is None:
                    conceder_conquista(user, rule)
                    TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                        evidencia_json={'evento_id': str(first.pk),
                                        'lancamento_id': first.agregado_id,
                                        'categoria': category},
                        definicao_json=rule.criterio_json)
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                _suspender_recompensas_sem_direito(grant, now)


def _aventuras_comprovadas(user):
    """Fatos únicos com quantidade igual ao ledger de mesa ainda válido."""
    from .models import TbEventoConquista, TbPersonagemAventura

    facts = list(TbEventoConquista.objects.filter(
        conta=user, origem='site_ledger', tipo='adventure_recorded'
    ).order_by('ocorrido_em', 'agregado_id'))
    ledgers = {row['pk']: row for row in
               TbPersonagemAventura.objects.filter(
                   id_personagem__dono=user, pk__in=[f.agregado_id for f in facts],
                   origem='mesa', revertido=False, qtd_aventuras__gt=0,
               ).values('pk', 'qtd_aventuras', 'id_personagem_id')}
    matched = []
    seen = set()
    for fact in facts:
        payload = fact.payload_json if isinstance(fact.payload_json, dict) else {}
        quantity = payload.get('quantidade')
        ledger = ledgers.get(fact.agregado_id)
        if (fact.agregado_id in seen or fact.versao_payload != 1 or
                fact.chave_origem != f'aventura-ledger:{fact.agregado_id}:registrada' or
                type(payload.get('ledger_id')) is not int or
                payload['ledger_id'] != fact.agregado_id or
                type(quantity) is not int or quantity <= 0 or
                ledger is None or ledger['qtd_aventuras'] != quantity or
                ledger['id_personagem_id'] != fact.personagem_id):
            continue
        seen.add(fact.agregado_id)
        matched.append(fact)
    return sum(f.payload_json['quantidade'] for f in matched), matched


def avaliar_aventuras_jogadas(user):
    """Reavalia marcos por quantidade de mesas com fato e ledger válidos."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbConquista,
                         TbUsuarioConquista, TbUsuarioCosmetico)

    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        rules = [rule for rule in TbConquista.objects.filter(
            ativo=True, criterio='automatico',
            criterio_json__metric='adventures_played').select_related('recompensa')
            if regra_aventuras_jogadas_valida(rule.criterio_json)]
        if not rules:
            return
        total, matched = _aventuras_comprovadas(user)
        evidence = {'total': total, 'evento_ids': [str(f.pk) for f in matched],
                    'lancamento_ids': [f.agregado_id for f in matched]}
        for rule in rules:
            definition = rule.criterio_json
            achieved = (total > definition['target'] if definition['operator'] == 'gt'
                        else total >= definition['target'])
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if achieved:
                if grant is None or grant.concedida_por_id is None:
                    conceder_conquista(user, rule)
                    TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                        evidencia_json=evidence, definicao_json=definition)
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                _suspender_recompensas_sem_direito(grant, now)


def validar_vinculo_aventura_bot(personagem, bot_quest_id, quantidade):
    """Aceita apenas a identidade exata de uma missão finalizada do participante.

    Deve ser chamado sob lock da conta antes do crédito. Nome/data jamais servem de
    identidade; o vínculo fica no ledger do site e no fato canônico correspondente.
    """
    from django.utils import timezone
    from .models import BotQuest, TbPersonagemAventura, UserProfile

    quest_id = (bot_quest_id or '').strip()
    if not quest_id:
        return None
    perfil = UserProfile.objects.filter(user_id=personagem.dono_id).only('discord_user_id').first()
    discord_id = (perfil.discord_user_id or '') if perfil else ''
    if not discord_id:
        raise ValueError('Conta sem vínculo Discord verificado.')
    quest = BotQuest.objects.filter(pk=quest_id, status='finished').only(
        'id', 'questPlayers', 'rewardAventurasOverride', 'endDate').first()
    if quest is None:
        raise ValueError('Missão do bot inexistente ou não finalizada.')
    player = next((player for player in (quest.questPlayers or [])
                   if isinstance(player, dict) and str(player.get('userId')) == discord_id), None)
    if player is None:
        raise ValueError('Conta não consta entre os participantes confirmados da missão.')
    if player.get('removedAt'):
        if not player.get('removedWithReward') or type(player.get('rewardAmount')) is not int or player['rewardAmount'] <= 0:
            raise ValueError('Participante removido sem recompensa verificável.')
        recompensa = player['rewardAmount']
        origem_recompensa = 'partial_removal'
        finalizada_em = player.get('removedAt')
    else:
        from django.utils.dateparse import parse_datetime
        finalizada_em = player.get('rewardFinalizedAt')
        try:
            data_prova = parse_datetime(finalizada_em) if isinstance(finalizada_em, str) else None
        except ValueError:
            data_prova = None
        recompensa = player.get('rewardAmount')
        if not data_prova or not data_prova.tzinfo:
            # Contrato anterior: override explícito da missão finalizada, aplicado
            # ao participante ativo. Mantém o vínculo, mas não prova crédito
            # individual para o agregado novo.
            if (type(quest.rewardAventurasOverride) is not int or
                    quest.rewardAventurasOverride <= 0):
                raise ValueError('Missão finalizada sem recompensa individual comprovada pelo bot.')
            recompensa = quest.rewardAventurasOverride
            origem_recompensa = 'legacy_quest_override'
            finalizada_em = None
        elif type(recompensa) is not int or recompensa <= 0:
            raise ValueError('Missão finalizada sem recompensa individual comprovada pelo bot.')
        else:
            origem_recompensa = player.get('rewardSource') or 'quest_finish'
            if origem_recompensa not in {'quest_finish', 'staff_override'}:
                raise ValueError('Origem da recompensa da missão inválida.')
        if (quest.rewardAventurasOverride is not None and
                recompensa != quest.rewardAventurasOverride):
            raise ValueError('Recompensa individual diverge da configuração atual da missão.')
    if int(quantidade) != recompensa:
        raise ValueError('Quantidade diferente das aventuras concedidas pela missão do bot.')
    if TbPersonagemAventura.objects.filter(
            id_personagem__dono_id=personagem.dono_id, revertido=False,
            detalhes_json__bot_quest_id=quest_id).exclude(
                origem='recompensa_comunidade').exists():
        raise ValueError('Esta missão do bot já foi vinculada a um lançamento ativo da conta.')
    return {
        'bot_quest_id': quest_id,
        'bot_quest_proof': {
            'discord_user_id': discord_id,
            'quest_end_at': quest.endDate.isoformat() if getattr(quest, 'endDate', None) else None,
            'removed_with_reward': bool(player.get('removedAt')),
            'reward_amount': recompensa,
            'reward_source': origem_recompensa,
            'reward_finalized_at': finalizada_em,
            'verified_at': timezone.now().isoformat(),
        },
    }


def _payload_compra(transacao, *, historica=False):
    """Reconstrói a identidade da compra diretamente do ledger financeiro."""
    import re

    def positive_id(value):
        if type(value) is int:
            number = value
        elif isinstance(value, str) and re.fullmatch(r'[0-9]+', value.strip()):
            number = int(value.strip())
        else:
            raise ValueError('Compra sem identidade de item e quantidade.')
        if number <= 0:
            raise ValueError('Compra sem identidade de item e quantidade.')
        return number

    if (transacao.tipo not in {'compra', 'mercado-compra'} or
            (transacao.revertida and not (historica and transacao.revertida_em)) or
            int(transacao.valor_pc) >= 0):
        raise ValueError('Transação não é uma compra válida de item.')
    detalhes = transacao.detalhes_json or {}
    if not isinstance(detalhes, dict):
        raise ValueError('Compra sem catálogo estruturado.')
    catalogo = detalhes.get('catalogo')
    if catalogo not in {'mundano', 'magico', 'oficina', 'comunidade'}:
        raise ValueError('Compra sem catálogo estruturado.')
    if (transacao.tipo == 'mercado-compra') != (catalogo == 'comunidade'):
        raise ValueError('Origem da compra inconsistente com o ledger.')
    try:
        catalogo_id = positive_id(detalhes.get('catalogo_id'))
        inventario_id = positive_id(detalhes.get('inventario_id'))
        quantidade = positive_id(detalhes.get('qtd'))
    except (TypeError, ValueError):
        raise ValueError('Compra sem identidade de item e quantidade.') from None
    payload = {
        'transacao_id': transacao.pk, 'catalogo': catalogo,
        'catalogo_id': catalogo_id, 'inventario_id': inventario_id,
        'quantidade': quantidade, 'valor_pc': int(transacao.valor_pc),
    }
    if catalogo == 'comunidade':
        try:
            anuncio_id = positive_id(detalhes.get('anuncio_id'))
        except (TypeError, ValueError):
            raise ValueError('Compra comunitária sem identidade do anúncio.') from None
        payload['anuncio_id'] = anuncio_id
    return payload


def registrar_fato_compra(transacao, *, historica=False):
    """Registra uma compra de item rastreável pelo ledger, nunca pela posse atual."""
    from .models import TbEventoConquista

    payload = _payload_compra(transacao, historica=historica)
    personagem = transacao.id_personagem
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_market', chave_origem=f'compra:{transacao.pk}:realizada',
        defaults={
            'tipo': 'item_purchased', 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': transacao.pk,
            'ocorrido_em': transacao.criado_em, 'payload_json': payload,
        },
    )
    if (evento.tipo != 'item_purchased' or evento.conta_id != personagem.dono_id or
            evento.agregado_id != transacao.pk or evento.payload_json != payload):
        raise ValueError('Identidade do fato de compra inconsistente.')
    if not historica:
        _avaliar_primeira_compra(personagem.dono)
        _avaliar_unidades_compradas(personagem.dono)
    return evento


def _compras_comprovadas(user):
    """Fatos únicos de compras ativas cuja identidade ainda coincide com o ledger."""
    from .models import TbEventoConquista, TbTransacao

    facts = list(TbEventoConquista.objects.filter(
        conta=user, origem='site_market', tipo='item_purchased'
    ).order_by('ocorrido_em', 'agregado_id', 'pk'))
    transactions = {purchase.pk: purchase for purchase in
                    TbTransacao.objects.filter(
                        id_personagem__dono=user, revertida=False,
                        pk__in=[fact.agregado_id for fact in facts]
                    )}
    matched = []
    seen = set()
    for fact in facts:
        purchase = transactions.get(fact.agregado_id)
        if (purchase is None or purchase.pk in seen or fact.versao_payload != 1 or
                fact.personagem_id != purchase.id_personagem_id or
                fact.chave_origem != f'compra:{purchase.pk}:realizada'):
            continue
        try:
            expected = _payload_compra(purchase)
        except ValueError:
            continue
        if fact.payload_json != expected:
            continue
        seen.add(purchase.pk)
        matched.append(fact)
    return matched


def registrar_fato_estorno_compra(compra, reembolso):
    """O estorno só existe após a reversão efetiva da compra e o crédito no ledger."""
    from .models import TbEventoConquista

    if (not compra.revertida or compra.revertida_em is None or
            reembolso.tipo != 'ajuste' or
            reembolso.id_personagem_id != compra.id_personagem_id or
            (reembolso.detalhes_json or {}).get('reverte_transacao') != compra.pk or
            int(reembolso.valor_pc) != -int(compra.valor_pc)):
        raise ValueError('Reembolso sem reversão financeira correspondente.')
    compra_fato = registrar_fato_compra(compra, historica=True)
    payload = {
        'transacao_id': compra.pk, 'reembolso_transacao_id': reembolso.pk,
        'compra_evento_id': str(compra_fato.pk),
        'quantidade': compra_fato.payload_json['quantidade'],
    }
    personagem = compra.id_personagem
    evento, _ = TbEventoConquista.objects.get_or_create(
        origem='site_market', chave_origem=f'compra:{compra.pk}:reembolsada',
        defaults={
            'tipo': 'item_purchase_refunded', 'conta_id': personagem.dono_id,
            'personagem': personagem, 'agregado_id': compra.pk,
            'ocorrido_em': compra.revertida_em, 'payload_json': payload,
        },
    )
    if (evento.tipo != 'item_purchase_refunded' or evento.conta_id != personagem.dono_id or
            evento.agregado_id != compra.pk or evento.payload_json != payload):
        raise ValueError('Identidade do fato de estorno inconsistente.')
    _avaliar_primeira_compra(personagem.dono)
    _avaliar_unidades_compradas(personagem.dono)
    return evento


def _avaliar_primeira_compra(user):
    """Reavalia compras rastreáveis não estornadas sob bloqueio da conta.

    A concessão permanece como histórico quando perde suporte; a posse visual é
    suspensa apenas quando a própria conquista é sua origem registrada.
    """
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbConquista,
                         TbUsuarioConquista, TbUsuarioCosmetico)

    regra = {'schema_version': 1, 'metric': 'items_purchased',
             'scope': 'account', 'operator': 'gte', 'target': 1}
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        facts = _compras_comprovadas(user)
        first = facts[0] if facts else None
        rules = TbConquista.objects.filter(
            ativo=True, criterio='automatico', criterio_json__metric='items_purchased'
        ).select_related('recompensa')
        for rule in rules:
            if rule.criterio_json != regra:
                continue
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if first is not None:
                if grant is None or (grant.revogada_em and grant.concedida_por_id is None):
                    if conceder_conquista(user, rule):
                        TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                            evidencia_json={'evento_id': str(first.pk), 'origem': first.origem,
                                            'chave_origem': first.chave_origem,
                                            'agregado_id': first.agregado_id},
                            definicao_json=regra)
                elif (grant.concedida_por_id is None and
                      grant.evidencia_json.get('agregado_id') != first.agregado_id):
                    grant.evidencia_json = {
                        'evento_id': str(first.pk), 'origem': first.origem,
                        'chave_origem': first.chave_origem,
                        'agregado_id': first.agregado_id,
                    }
                    grant.save(update_fields=['evidencia_json'])
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                _suspender_recompensas_sem_direito(grant, now)


def _avaliar_unidades_compradas(user):
    """Conta unidades pagas de IDs configurados; estornos retiram suporte da concessão."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from .models import (CosmeticCheckoutPurchase, TbConquista,
                         TbUsuarioConquista, TbUsuarioCosmetico)

    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        rules = [rule for rule in TbConquista.objects.filter(
            ativo=True, criterio='automatico',
            criterio_json__metric='items_purchased_units').select_related('recompensa')
            if regra_unidades_compradas_valida(rule.criterio_json)]
        if not rules:
            return
        facts = _compras_comprovadas(user)
        for rule in rules:
            definition = rule.criterio_json
            identities = {(item['catalog'], item['id'])
                          for item in definition['filters']['items']}
            matched = [fact for fact in facts if
                       (fact.payload_json.get('catalogo'),
                        fact.payload_json.get('catalogo_id')) in identities and
                       type(fact.payload_json.get('quantidade')) is int and
                       fact.payload_json['quantidade'] > 0]
            total = sum(fact.payload_json['quantidade'] for fact in matched)
            achieved = (total > definition['target'] if definition['operator'] == 'gt'
                        else total >= definition['target'])
            grant = TbUsuarioConquista.objects.select_for_update().filter(
                user=user, conquista=rule).first()
            if achieved:
                if grant is None or grant.concedida_por_id is None:
                    conceder_conquista(user, rule)
                    evidence = {'total': total, 'evento_ids': [str(fact.pk) for fact in matched],
                                'transacao_ids': [fact.agregado_id for fact in matched]}
                    TbUsuarioConquista.objects.filter(user=user, conquista=rule).update(
                        evidencia_json=evidence, definicao_json=definition)
            elif grant and grant.concedida_por_id is None and grant.revogada_em is None:
                now = timezone.now()
                grant.revogada_em = now
                grant.save(update_fields=['revogada_em'])
                _suspender_recompensas_sem_direito(grant, now)


def reprocessar_primeira_compra(user):
    """Recria fatos apenas de compras ativas com ledger estruturado comprovável."""
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from .models import TbEventoConquista, TbTransacao

    novas = invalidas = 0
    with transaction.atomic():
        get_user_model().objects.select_for_update().only('pk').get(pk=user.pk)
        purchases = TbTransacao.objects.filter(
            id_personagem__dono=user, revertida=False,
            tipo__in=['compra', 'mercado-compra'], valor_pc__lt=0,
        ).select_related('id_personagem').order_by('pk')
        for purchase in purchases:
            existed = TbEventoConquista.objects.filter(
                origem='site_market', chave_origem=f'compra:{purchase.pk}:realizada').exists()
            try:
                registrar_fato_compra(purchase, historica=True)
            except ValueError:
                invalidas += 1
                continue
            novas += int(not existed)
        _avaliar_primeira_compra(user)
        _avaliar_unidades_compradas(user)
    return {'novas': novas, 'invalidas': invalidas}


def progresso_aventuras_por_origem(user, discord_user_id=None):
    """Mostra fontes distintas e soma só créditos de missão sem sobreposição possível."""
    from django.db.models import Sum
    from django.db import DatabaseError, transaction
    from .models import BotCharacterLog, BotQuest, TbPersonagem, TbPersonagemAventura

    personagens = list(TbPersonagem.objects.filter(dono=user).values_list(
        'pk', 'aventuras'))
    lancamentos = list(TbPersonagemAventura.objects.filter(
        id_personagem__dono=user, qtd_aventuras__gt=0
    ).exclude(origem='recompensa_comunidade').values(
        'id_personagem_id', 'qtd_aventuras', 'detalhes_json', 'revertido'))
    recompensas_comunidade = dict(
        TbPersonagemAventura.objects.filter(
            id_personagem__dono=user, revertido=False,
            origem='recompensa_comunidade', qtd_aventuras__gt=0,
        ).values('id_personagem_id').annotate(total=Sum('qtd_aventuras')).values_list(
            'id_personagem_id', 'total'))
    por_personagem = {}
    vinculadas_ao_bot = 0
    vinculadas_por_id = {}
    site_sem_vinculo = 0
    vinculos_duplicados = 0
    vinculos_estornados = set()
    for row in lancamentos:
        bot_id = (row['detalhes_json'] or {}).get('bot_quest_id')
        if row['revertido']:
            if bot_id:
                vinculos_estornados.add(bot_id)
            continue
        quantidade = int(row['qtd_aventuras'])
        pk = row['id_personagem_id']
        por_personagem[pk] = por_personagem.get(pk, 0) + quantidade
        if bot_id:
            vinculadas_ao_bot += quantidade
            if bot_id in vinculadas_por_id:
                vinculos_duplicados += 1
            vinculadas_por_id[bot_id] = quantidade
        else:
            site_sem_vinculo += quantidade
    site_total = sum(por_personagem.values())
    saldo_sem_ledger = sum(max(
        0, int(saldo or 0) - int(recompensas_comunidade.get(pk, 0) or 0)
        - por_personagem.get(pk, 0))
                           for pk, saldo in personagens)
    divergencias = sum(
        int(saldo or 0) - int(recompensas_comunidade.get(pk, 0) or 0)
        < por_personagem.get(pk, 0)
                      for pk, saldo in personagens)
    bot_logs, bot_disponivel = [], True
    bot_creditos = {}
    bot_creditos_disponiveis = True
    bot_sem_prova = 0
    if discord_user_id:
        try:
            # A tabela do bot é externa (managed=False) e pode não estar montada.
            with transaction.atomic():
                bot_logs = list(BotCharacterLog.objects.filter(
                    discordUserId=discord_user_id).order_by('id').values(
                        'id', 'characterName', 'adventuresPlayed'))
        except DatabaseError:
            bot_disponivel = False
        try:
            with transaction.atomic():
                quests = BotQuest.objects.filter(
                    status='finished', questPlayers__contains=[{'userId': discord_user_id}]
                ).values('id', 'questPlayers')
                for quest in quests:
                    players = [p for p in (quest['questPlayers'] or [])
                               if isinstance(p, dict) and str(p.get('userId')) == discord_user_id]
                    if len(players) != 1:
                        bot_sem_prova += 1
                        continue
                    player = players[0]
                    amount = player.get('rewardAmount')
                    if (type(amount) is not int or amount <= 0 or
                            (player.get('removedAt') and not player.get('removedWithReward')) or
                            (not player.get('removedAt') and not player.get('rewardFinalizedAt'))):
                        bot_sem_prova += 1
                        continue
                    bot_creditos[quest['id']] = amount
        except DatabaseError:
            bot_creditos_disponiveis = False
    bot_apenas = sum(qtd for quest_id, qtd in bot_creditos.items()
                     if quest_id not in vinculadas_por_id and quest_id not in vinculos_estornados)
    conflitos = sum(bot_creditos[quest_id] != qtd
                    for quest_id, qtd in vinculadas_por_id.items()
                    if quest_id in bot_creditos) + vinculos_duplicados
    total_conciliado = (site_total + bot_apenas
                       if discord_user_id and bot_creditos_disponiveis and
                       bot_sem_prova == 0 and conflitos == 0 and
                       not (site_sem_vinculo and bot_apenas) else None)
    return {
        'site_total': site_total,
        'site_vinculadas_ao_bot': vinculadas_ao_bot,
        'saldo_sem_ledger': saldo_sem_ledger,
        'divergencias': divergencias,
        'bot_logs': bot_logs,
        'bot_disponivel': bot_disponivel,
        'bot_creditos_disponiveis': bot_creditos_disponiveis,
        'bot_creditos_por_missao': len(bot_creditos),
        'bot_creditos_adicionais': bot_apenas,
        'bot_creditos_estornados': sum(quest_id in bot_creditos and quest_id not in vinculadas_por_id
                                      for quest_id in vinculos_estornados),
        'bot_sem_prova': bot_sem_prova,
        'conflitos_vinculo': conflitos,
        'total_conciliado': total_conciliado,
        'discord_vinculado': bool(discord_user_id),
    }


# ─────────────────────────── Vitrine (perfil) ──────────────────────────────────
def _conquista_dict(conquista, obtida, concedida_em=None):
    """Dict uniforme pros templates de vitrine."""
    return {
        'slug': conquista.slug,
        'nome': conquista.nome,
        'descricao': conquista.descricao or '',
        # Ícone efetivo: arquivo enviado (icone_file) > icone_url. O template
        # continua com o fallback 🏆 quando vazio.
        'icone_url': conquista.icone_efetivo,
        'secreta': conquista.secreta,
        'obtida': obtida,
        'concedida_em': concedida_em,
    }


def _slugs_obtidas(user):
    """Mapa {conquista_id: concedida_em} das conquistas que o usuário TEM."""
    from .models import TbUsuarioConquista
    return dict(
        TbUsuarioConquista.objects
        .filter(user=user, conquista__ativo=True, revogada_em__isnull=True)
        .values_list('conquista_id', 'concedida_em')
    )


def visibilidade_conquistas_de_personagem(users):
    """Marcos de classe/nível publicáveis e recompensas a ocultar por conta."""
    from .models import (CosmeticCheckoutPurchase, TbConquista, TbCosmetico,
                         TbPersonagem, TbUsuarioConquista, TbUsuarioCosmetico)

    ids = [user.pk for user in users if getattr(user, 'pk', None)]
    publicas = {user_id: set() for user_id in ids}
    ocultas = {user_id: set() for user_id in ids}
    if not ids:
        return publicas, ocultas
    all_grants = list(TbUsuarioConquista.objects.filter(
        user_id__in=ids, conquista__ativo=True, revogada_em__isnull=True,
    ).values('user_id', 'conquista_id', 'conquista__criterio_json', 'evidencia_json'))
    rewards_by_conquest = {}
    for conquest in TbConquista.objects.filter(
            pk__in={grant['conquista_id'] for grant in all_grants}).select_related(
                'recompensa').prefetch_related('recompensas_extras'):
        slugs = {item.slug for item in conquest.recompensas_extras.all()}
        if conquest.recompensa_id:
            slugs.add(conquest.recompensa.slug)
        rewards_by_conquest[conquest.pk] = slugs
    private_metrics = {'class_started', 'character_level', 'rank_reached'}
    grants = [grant for grant in all_grants if isinstance(
        grant['conquista__criterio_json'], dict) and
        grant['conquista__criterio_json'].get('metric') in private_metrics]
    sources = set()
    for grant in grants:
        evidence = grant['evidencia_json']
        source_ids = (evidence.get('personagem_ids') if isinstance(evidence, dict)
                      else None)
        if not isinstance(source_ids, list):
            source_id = (evidence.get('personagem_id', evidence.get('agregado_id'))
                         if isinstance(evidence, dict) else None)
            source_ids = [source_id]
        source_ids = [source_id for source_id in source_ids if type(source_id) is int]
        sources.update(source_ids)
        grant['source_ids'] = source_ids
    visible_sources = set(TbPersonagem.objects.filter(
        pk__in=sources, dono_id__in=ids, publico=True, arquivado=False,
    ).values_list('dono_id', 'pk'))
    visible_rewards = {user_id: set() for user_id in ids}
    for grant in grants:
        user_id = grant['user_id']
        reward_slugs = rewards_by_conquest.get(grant['conquista_id'], set())
        if any((user_id, source_id) in visible_sources
               for source_id in grant['source_ids']):
            publicas[user_id].add(grant['conquista_id'])
            visible_rewards[user_id].update(reward_slugs)
        else:
            ocultas[user_id].update(reward_slugs)
    candidate_slugs = set().union(*ocultas.values())
    if candidate_slugs:
        for grant in all_grants:
            criterion = grant['conquista__criterio_json']
            if not isinstance(criterion, dict) or criterion.get('metric') not in private_metrics:
                visible_rewards[grant['user_id']].update(
                    rewards_by_conquest.get(grant['conquista_id'], set()) & candidate_slugs)
        purchases = CosmeticCheckoutPurchase.objects.filter(
            beneficiary_id__in=ids, cosmetico__slug__in=candidate_slugs,
            granted_at__isnull=False,
        ).values_list('beneficiary_id', 'cosmetico__slug')
        for user_id, slug in purchases:
            visible_rewards[user_id].add(slug)
        other_inventory = (TbUsuarioCosmetico.objects.filter(
            user_id__in=ids, cosmetico__slug__in=candidate_slugs,
            suspenso_em__isnull=True,
        ).exclude(origem__startswith='conquista:').exclude(origem='')
          .values_list('user_id', 'cosmetico__slug'))
        for user_id, slug in other_inventory:
            visible_rewards[user_id].add(slug)
        free_slugs = set(TbCosmetico.objects.filter(
            slug__in=candidate_slugs, ativo=True, origem='livre',
        ).values_list('slug', flat=True))
        for user_id in ids:
            visible_rewards[user_id].update(free_slugs)
    for user_id in ids:
        ocultas[user_id].difference_update(visible_rewards[user_id])
    return publicas, ocultas


# Nome anterior mantido para consumidores já existentes.
visibilidade_inicio_classe = visibilidade_conquistas_de_personagem


def _evidencias_privadas_de_personagens(user):
    """Prepara provas registradas de classe, nível e rank para dono/staff."""
    from .models import TbPersonagem, TbUsuarioConquista

    grants = list(TbUsuarioConquista.objects.filter(
        user=user, revogada_em__isnull=True, conquista__ativo=True,
        conquista__criterio='automatico', concedida_por__isnull=True,
        conquista__criterio_json__metric__in=(
            'class_started', 'character_level', 'rank_reached'),
    ).select_related('conquista').order_by('conquista__ordem', 'conquista__nome'))
    sources = set()
    rows = []
    for grant in grants:
        evidence = grant.evidencia_json
        if not isinstance(evidence, dict):
            continue
        metric = grant.conquista.criterio_json.get('metric')
        ids = evidence.get('personagem_ids')
        if not isinstance(ids, list):
            source = (evidence.get('agregado_id') if metric == 'class_started'
                      else evidence.get('personagem_id'))
            ids = [source]
        ids = sorted({source for source in ids if type(source) is int and source > 0})
        fact_id = evidence.get('evento_id')
        if not ids and not fact_id:
            continue
        sources.update(ids)
        rows.append((grant, evidence, ids))
    names = dict(TbPersonagem.objects.filter(
        pk__in=sources, dono=user).values_list('pk', 'nome'))
    return [{
        'nome': grant.conquista.nome,
        'fontes': [f'{names[source]} (#{source})' if source in names
                   else f'Ficha excluída (#{source})' for source in ids],
        'nivel': evidence.get('nivel') if type(evidence.get('nivel')) is int else None,
        'rank': evidence.get('rank') if type(evidence.get('rank')) is str else None,
        'evento_id': evidence.get('evento_id') if
            isinstance(evidence.get('evento_id'), str) else None,
    } for grant, evidence, ids in rows]


def conquistas_do_usuario(user, incluir_bloqueadas=True, *, pode_ver_privados=True):
    """Estado das conquistas ATIVAS de `user` pra vitrine.

    Retorna dict:
        {
          'obtidas': [dict...],        # concedidas (com data), ordenadas por concessão desc
          'bloqueadas': [dict...],     # não-secretas não-obtidas (se incluir_bloqueadas)
          'total': int,                # Y do contador "X / Y" (ver regra abaixo)
          'obtidas_count': int,        # X do contador
        }

    Regra do contador Y: total de conquistas ATIVAS não-secretas + as SECRETAS que
    o user tem. Secretas NÃO-obtidas nunca contam nem aparecem (não vaza existência).
    """
    vazio = {'obtidas': [], 'bloqueadas': [], 'total': 0, 'obtidas_count': 0,
             'evidencias_privadas': []}
    if not user or not getattr(user, 'pk', None):
        return vazio
    from .models import TbConquista

    obtidas_map = _slugs_obtidas(user)  # {conquista_id: data}
    marcos_publicos = (visibilidade_conquistas_de_personagem([user])[0][user.pk]
                       if not pode_ver_privados else set())
    qs = (TbConquista.objects.filter(ativo=True)
          .order_by('ordem', 'nome'))

    obtidas, bloqueadas = [], []
    total_visivel = 0
    aventuras_comprovadas = None
    compras_comprovadas = None
    niveis_comprovados = None
    niveis_classe_unica = None
    quests_comprovadas = None
    rank_sources = None
    for c in qs:
        if (not pode_ver_privados and isinstance(c.criterio_json, dict) and
                c.criterio_json.get('metric') in {'class_started', 'character_level',
                                                   'rank_reached'} and
                c.id not in marcos_publicos):
            continue
        tem = c.id in obtidas_map
        if c.secreta and not tem:
            # Secreta não-obtida: invisível — não conta, não aparece.
            continue
        total_visivel += 1
        item = _conquista_dict(c, tem, obtidas_map.get(c.id))
        if (pode_ver_privados and isinstance(c.criterio_json, dict) and
                regra_aventuras_jogadas_valida(c.criterio_json)):
            if aventuras_comprovadas is None:
                aventuras_comprovadas, _ = _aventuras_comprovadas(user)
            item['progresso_aventuras'] = {
                'atual': aventuras_comprovadas,
                'alvo': c.criterio_json['target'],
                'operador': c.criterio_json['operator'],
            }
        if (pode_ver_privados and isinstance(c.criterio_json, dict) and
                regra_unidades_compradas_valida(c.criterio_json)):
            if compras_comprovadas is None:
                compras_comprovadas = _compras_comprovadas(user)
            identities = {(identity['catalog'], identity['id'])
                          for identity in c.criterio_json['filters']['items']}
            item['progresso_unidades'] = {
                'atual': sum(fact.payload_json['quantidade']
                             for fact in compras_comprovadas
                             if (fact.payload_json['catalogo'],
                                 fact.payload_json['catalogo_id']) in identities),
                'alvo': c.criterio_json['target'],
                'operador': c.criterio_json['operator'],
            }
        if (pode_ver_privados and isinstance(c.criterio_json, dict) and
                regra_nivel_personagem_valida(c.criterio_json)):
            if c.criterio_json['filters'].get('single_class'):
                if niveis_classe_unica is None:
                    niveis_classe_unica = _niveis_comprovados(user, single_class=True)
                proof = niveis_classe_unica
            else:
                if niveis_comprovados is None:
                    niveis_comprovados = _niveis_comprovados(user)
                proof = niveis_comprovados
            item['progresso_nivel'] = {
                'atual': proof.get(
                    c.criterio_json['filters']['class_slug'], (0, None))[0],
                'alvo': c.criterio_json['target'],
            }
        if (pode_ver_privados and isinstance(c.criterio_json, dict) and
                regra_rank_valida(c.criterio_json)):
            if rank_sources is None:
                rank_sources = _marcos_rank_comprovados(user)
            if niveis_comprovados is None:
                niveis_comprovados = _niveis_comprovados(user)
            level = max(rank_sources[0][0] if rank_sources else 0,
                        max((row[0] for row in niveis_comprovados.values()), default=0))
            item['progresso_rank'] = {
                'atual': level,
                'alvo': ranks_verificaveis()[c.criterio_json['filters']['rank']],
            }
        if (pode_ver_privados and isinstance(c.criterio_json, dict) and
                regra_quest_categorizada_valida(c.criterio_json)):
            if quests_comprovadas is None:
                quests_comprovadas = _quests_comprovadas(user)
            item['progresso_quest'] = {
                'atual': len(quests_comprovadas[c.criterio_json['filters']['category']]),
                'alvo': c.criterio_json['target'],
            }
        if tem:
            obtidas.append(item)
        elif incluir_bloqueadas:
            bloqueadas.append(item)

    # Obtidas mais recentes primeiro (X é o número delas).
    obtidas.sort(key=lambda d: d['concedida_em'] or 0, reverse=True)
    return {
        'obtidas': obtidas,
        'bloqueadas': bloqueadas,
        'total': total_visivel,
        'obtidas_count': len(obtidas),
        'evidencias_privadas': (_evidencias_privadas_de_personagens(user)
                                if pode_ver_privados else []),
    }


def conquistas_batch(users):
    """Pro /jogadores/ (opcional): {user_pk: obtidas_count} numa query. Evita N+1
    quando o card mostra o contador de conquistas."""
    users = list(users)
    out = {u.pk: 0 for u in users}
    if not users:
        return out
    from django.db.models import Count
    from .models import TbUsuarioConquista
    linhas = (TbUsuarioConquista.objects
              .filter(user_id__in=[u.pk for u in users], conquista__ativo=True,
                      revogada_em__isnull=True)
              .values('user_id')
              .annotate(n=Count('id')))
    for row in linhas:
        out[row['user_id']] = row['n']
    return out
