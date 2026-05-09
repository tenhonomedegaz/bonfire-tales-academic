

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0002_raca'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbMapMarker',
            fields=[
                ('id_marker', models.AutoField(db_column='Id_Marker', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150)),
                ('markdown', models.TextField(blank=True, db_column='Markdown', help_text='Todo o texto lateral formatado em Markdown.', null=True)),
                ('lat', models.FloatField(db_column='Latitude', help_text='Ponto Y / Cima pra baixo no mapa customizado.')),
                ('lng', models.FloatField(db_column='Longitude', help_text='Ponto X / Esquerda pra direita no mapa customizado.')),
                ('icone', models.CharField(choices=[('azul', 'Castelo Azul'), ('vermelho', 'Castelo Vermelho'), ('laranja', 'Castelo Laranja'), ('verde', 'Castelo Verde'), ('roxo', 'Castelo Roxo'), ('preto_castelo', 'Castelo Preto'), ('caveira', 'Caveira'), ('ancora', 'Âncora'), ('patinha', 'Pata'), ('amarelo', 'Castelo Amarelo'), ('branco', 'Castelo Branco')], db_column='Icone', default='azul', max_length=50)),
            ],
            options={
                'db_table': 'TB_MapMarker',
            },
        ),
    ]
