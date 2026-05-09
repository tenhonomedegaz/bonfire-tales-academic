

from django.db import migrations
from django.utils.text import slugify


def forwards(apps, schema_editor):
    TbMapMarker = apps.get_model('home', 'TbMapMarker')
    TbRegiao = apps.get_model('home', 'TbRegiao')

    existing_slugs = set(TbRegiao.objects.values_list('slug', flat=True))

    for marker in TbMapMarker.objects.all().order_by('nome'):
        slug = slugify(marker.nome)
        if not slug or slug in existing_slugs:
            continue

        TbRegiao.objects.create(
            nome=marker.nome,
            slug=slug,
            descricao_breve=marker.descricao_breve or '',
            territorio=marker.territorio or '',
            categoria=marker.categoria or 'cidade',
            faccao_dominante=marker.faccao_dominante or '',
            tecnologia=marker.tecnologia or '',
            magia=marker.magia or '',
            imagem_url=marker.imagem_url or '',
            token_color=marker.token_color or 'blue',
        )
        existing_slugs.add(slug)


def backwards(apps, schema_editor):
    
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0015_tbregiao'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
