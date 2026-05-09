

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0019_tbregiao_ameacas_externas_tbregiao_ameacas_internas_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='descricao_breve',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='faccao_dominante',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='imagem_url',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='lore_url',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='magia',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='markdown',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='pin_icon',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='tecnologia',
        ),
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='token_color',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='descricao_breve',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='faccao_dominante',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='imagem_url',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='magia',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='tecnologia',
        ),
        migrations.RemoveField(
            model_name='tbregiao',
            name='token_color',
        ),
        migrations.AlterField(
            model_name='tbmapmarker',
            name='categoria',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('fortaleza', 'Fortaleza'), ('conglomerado_vilas', 'Conglomerado de Vilas'), ('vila', 'Vila'), ('cidade_portuaria', 'Cidade Portuária'), ('area_selvagem', 'Área Selvagem')], db_column='Categoria', default='cidade', max_length=50),
        ),
        migrations.AlterField(
            model_name='tbregiao',
            name='categoria',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('fortaleza', 'Fortaleza'), ('conglomerado_vilas', 'Conglomerado de Vilas'), ('vila', 'Vila'), ('cidade_portuaria', 'Cidade Portuária'), ('area_selvagem', 'Área Selvagem')], db_column='Categoria', default='cidade', max_length=50),
        ),
    ]
