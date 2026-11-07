from django.db import migrations


# Frozen progression data: Lenda is a title, not an eighth rank.
RANKS = (
    ('obsidiana', 'Obsidiana', 1, 0),
    ('ametista', 'Ametista', 5, 9),
    ('topazio', 'Top\u00e1zio', 9, 28),
    ('esmeralda', 'Esmeralda', 13, 59),
    ('ambar', '\u00c2mbar', 17, 102),
    ('rubi', 'Rubi', 20, 140),
    ('diamante', 'Diamante', 21, 160),
)


def seed_rank_rewards(apps, schema_editor):
    alias = schema_editor.connection.alias
    Cosmetic = apps.get_model('home', 'TbCosmetico')
    Achievement = apps.get_model('home', 'TbConquista')
    for order, (key, name, level, adventures) in enumerate(RANKS):
        target = 'lvl 20 e o patamar Epic Boon' if level == 21 else f'lvl {level}'
        requirement = f'alcance {target} com um personagem pra liberar'
        rewards = []
        for variant in ('aberta', 'fechada'):
            cosmetic, _ = Cosmetic.objects.using(alias).get_or_create(
                slug=f'moldura-elo-{key}-{variant}', defaults={'tipo': 'moldura'})
            definition = (dict(cosmetic.definicao_json)
                          if isinstance(cosmetic.definicao_json, dict) else {})
            definition['desbloqueio'] = {
                'schema_version': 1, 'metric': 'rank_reached', 'rank': name,
                'min_level': min(level, 20), 'min_adventures': adventures,
                'permanent': True,
            }
            # Preserve PK, inventory, active/draft state and uploaded art.
            Cosmetic.objects.using(alias).filter(pk=cosmetic.pk).update(
                nome=f'Moldura Elo {name} - {variant}', tipo='moldura',
                css_class='frame-elo', origem='conquista', preco=None,
                # Catalog animation means ambient animation, not a hover transition.
                animado=False, escopo='ambos', ordem=200 + order * 2 + len(rewards),
                descricao=requirement, definicao_json=definition)
            rewards.append(cosmetic)
        rule, _ = Achievement.objects.using(alias).get_or_create(slug=f'elo-{key}')
        Achievement.objects.using(alias).filter(pk=rule.pk).update(
            nome=f'Elo {name}', descricao=requirement, criterio='automatico',
            criterio_json={'schema_version': 1, 'metric': 'rank_reached',
                           'scope': 'account', 'filters': {'rank': name},
                           'operator': 'gte', 'target': 1, 'retention': 'permanent'},
            recompensa_id=rewards[0].pk, ordem=200 + order)
        rule.recompensas_extras.add(rewards[1])


def backfill_rank_rewards(apps, schema_editor):
    """Historical-model reconciliation, inside the migration transaction."""
    alias = schema_editor.connection.alias
    Character = apps.get_model('home', 'TbPersonagem')
    Achievement = apps.get_model('home', 'TbConquista')
    Grant = apps.get_model('home', 'TbUsuarioConquista')
    Inventory = apps.get_model('home', 'TbUsuarioCosmetico')
    Notification = apps.get_model('home', 'TbConquistaNotificacao')
    best = {}
    for character in Character.objects.using(alias).prefetch_related('classes').iterator(chunk_size=200):
        rows = list(character.classes.all())
        if (not 1 <= character.nivel <= 20 or character.aventuras < 0 or not rows
                or sum(row.principal for row in rows) != 1
                or any(not 1 <= row.nivel <= 20 for row in rows)
                or sum(row.nivel for row in rows) != character.nivel):
            continue
        score = max((level for _, _, level, adventures in RANKS
                     if character.nivel >= min(level, 20)
                     and character.aventuras >= adventures), default=0)
        if score > best.get(character.dono_id, (0, None))[0]:
            best[character.dono_id] = (score, character)
    rules = Achievement.objects.using(alias).filter(
        slug__in=[f'elo-{key}' for key, _, _, _ in RANKS], ativo=True,
    ).prefetch_related('recompensas_extras')
    thresholds = {name: level for _, name, level, _ in RANKS}
    for rule in rules:
        prior = dict(Grant.objects.using(alias).filter(conquista=rule).values_list('user_id', 'pk'))
        for user_id in set(best) | set(prior):
            level, character = best.get(user_id, (0, None))
            if user_id not in prior and level < thresholds[rule.criterio_json['filters']['rank']]:
                continue
            grant, _ = Grant.objects.using(alias).get_or_create(
                user_id=user_id, conquista_id=rule.pk,
                defaults={'definicao_json': rule.criterio_json,
                          'evidencia_json': ({'personagem_id': character.pk,
                                             'nivel': character.nivel,
                                             'aventuras': character.aventuras}
                                            if character else {})})
            if grant.revogada_em is not None:
                continue
            Notification.objects.using(alias).get_or_create(concessao_id=grant.pk)
            rewards = set(rule.recompensas_extras.values_list('pk', flat=True))
            if rule.recompensa_id:
                rewards.add(rule.recompensa_id)
            for reward_id in rewards:
                Inventory.objects.using(alias).get_or_create(
                    user_id=user_id, cosmetico_id=reward_id,
                    defaults={'origem': f'conquista:{rule.slug}'})


class Migration(migrations.Migration):
    dependencies = [('home', '0163_tbpersonagem_public_default')]
    operations = [
        migrations.RunPython(seed_rank_rewards, migrations.RunPython.noop),
        migrations.RunPython(backfill_rank_rewards, migrations.RunPython.noop),
    ]
