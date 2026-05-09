

from django.db import migrations, models
from django.utils.text import slugify


def seed_territories_from_regions(apps, schema_editor):
    regiao = apps.get_model('home', 'TbRegiao')
    territorio = apps.get_model('home', 'TbTerritorio')
    names = sorted({(row.territorio or '').strip() for row in regiao.objects.all() if (row.territorio or '').strip()})

    for name in names:
        base_slug = slugify(name) or 'territorio'
        candidate = base_slug
        counter = 2
        while territorio.objects.filter(slug=candidate).exists():
            candidate = f'{base_slug}-{counter}'
            counter += 1

        territorio.objects.get_or_create(
            nome=name,
            defaults={
                'slug': candidate,
                'descricao_breve': '',
                'lore_markdown': '',
                'imagem_url': '',
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0017_add_brasao_url_to_regiao'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbTerritorio',
            fields=[
                ('id_territorio', models.AutoField(db_column='Id_Territorio', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150, unique=True)),
                ('slug', models.SlugField(db_column='Slug', max_length=160, unique=True)),
                ('descricao_breve', models.TextField(blank=True, db_column='DescricaoBreve', null=True)),
                ('lore_markdown', models.TextField(blank=True, db_column='LoreMarkdown', help_text='Lore do território em Markdown.', null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', help_text='URL ou caminho static da imagem de capa.', max_length=500, null=True)),
            ],
            options={
                'verbose_name': 'Território',
                'verbose_name_plural': 'Territórios',
                'db_table': 'TB_Territorio',
            },
        ),
        migrations.RunPython(seed_territories_from_regions, migrations.RunPython.noop),
    ]
