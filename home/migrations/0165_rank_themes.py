from importlib import import_module

from django.db import migrations


RANK_THEMES = (
    ('obsidiana', 'Obsidiana', 1, 0, 'facets', '#b7bec9', '#747f92'),
    ('ametista', 'Ametista', 5, 9, 'runes', '#a78bfa', '#7c3aed'),
    ('topazio', 'Top\u00e1zio', 9, 28, 'sun', '#facc15', '#f59e0b'),
    ('esmeralda', 'Esmeralda', 13, 59, 'leaves', '#34d399', '#059669'),
    ('ambar', '\u00c2mbar', 17, 102, 'flames', '#fbbf24', '#d97706'),
    ('rubi', 'Rubi', 20, 140, 'thorns', '#fb7185', '#e11d48'),
    ('diamante', 'Diamante', 21, 160, 'crystal', '#7dd3fc', '#38bdf8'),
)


def seed_rank_themes(apps, schema_editor):
    alias = schema_editor.connection.alias
    Cosmetic = apps.get_model('home', 'TbCosmetico')
    Achievement = apps.get_model('home', 'TbConquista')
    for order, (key, name, level, adventures, motif, accent, accent2) in enumerate(RANK_THEMES):
        rule = Achievement.objects.using(alias).filter(slug=f'elo-{key}').first()
        if rule is None:
            continue  # Do not recreate achievements deliberately removed by staff.
        if 'Elo ' in rule.nome:
            Achievement.objects.using(alias).filter(pk=rule.pk).update(
                nome=rule.nome.replace('Elo ', 'Rank ', 1))
        for variant in ('aberta', 'fechada'):
            frame = Cosmetic.objects.using(alias).filter(slug=f'moldura-elo-{key}-{variant}').first()
            if frame and 'Elo ' in frame.nome:
                Cosmetic.objects.using(alias).filter(pk=frame.pk).update(
                    nome=frame.nome.replace('Elo ', 'Rank ', 1))
        definition = {
            'accent': accent, 'accent2': accent2, 'surface': '#141418', 'deep': '#09090c',
            'gradiente': False, 'particula': 'nenhuma', 'vel': 'lenta', 'glow': False,
            'motif': motif,
        }
        unlock = {'schema_version': 1, 'metric': 'rank_reached', 'rank': name,
                  'min_level': min(level, 20), 'min_adventures': adventures, 'permanent': True}
        theme, _ = Cosmetic.objects.using(alias).get_or_create(
            slug=f'tema-rank-{key}', defaults={
                'nome': f'Rank {name}', 'tipo': 'tema', 'escopo': 'ambos',
                'origem': 'conquista', 'css_class': 'theme-data', 'ativo': True,
                'preco': None, 'asset_url': '', 'animado': False,
                'descricao': rule.descricao, 'ordem': 300 + order,
                'definicao_json': dict(definition, desbloqueio=unlock),
            })
        # Existing art, editorial settings, custom palette and staff state win.
        existing = theme.definicao_json if isinstance(theme.definicao_json, dict) else {}
        merged = dict(definition, **existing)
        merged['desbloqueio'] = unlock
        if theme.definicao_json != merged:
            Cosmetic.objects.using(alias).filter(pk=theme.pk).update(definicao_json=merged)
        rule.recompensas_extras.add(theme)


def backfill_rank_themes(apps, schema_editor):
    previous = import_module('home.migrations.0164_rank_cosmetic_rewards')
    previous.backfill_rank_rewards(apps, schema_editor)


class Migration(migrations.Migration):
    dependencies = [('home', '0164_rank_cosmetic_rewards')]
    operations = [
        migrations.RunPython(seed_rank_themes, migrations.RunPython.noop),
        migrations.RunPython(backfill_rank_themes, migrations.RunPython.noop),
    ]
