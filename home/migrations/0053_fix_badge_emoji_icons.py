# -*- coding: utf-8 -*-
"""Corrige ícones de badges do seed 0050 que apontavam para o MaxCDN (desativado).

`twemoji.maxcdn.com` foi descontinuado há anos — as imagens ficam pendentes para
sempre, quebrando o ícone do badge no perfil (e em produção). Trocamos a URL morta
pelo glyph emoji nativo, que `_concedida_dict` agora renderiza como texto (sem CDN).

Só toca linhas que AINDA apontam para a URL morta (idempotente; respeita edições
manuais posteriores).
"""
from django.db import migrations


# slug -> (url_morta, glyph)
FIX = {
    'badge-matador-dragoes': ('https://twemoji.maxcdn.com/v/latest/72x72/1f409.png', '🐉'),
    'badge-primeira-fogueira': ('https://twemoji.maxcdn.com/v/latest/72x72/1f525.png', '🔥'),
}


def _forward(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    for slug, (url_morta, glyph) in FIX.items():
        TbCosmetico.objects.filter(slug=slug, asset_url=url_morta).update(asset_url=glyph)


def _backward(apps, schema_editor):
    TbCosmetico = apps.get_model('home', 'TbCosmetico')
    for slug, (url_morta, glyph) in FIX.items():
        TbCosmetico.objects.filter(slug=slug, asset_url=glyph).update(asset_url=url_morta)


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0052_seed_conquistas'),
    ]

    operations = [
        migrations.RunPython(_forward, _backward),
    ]
