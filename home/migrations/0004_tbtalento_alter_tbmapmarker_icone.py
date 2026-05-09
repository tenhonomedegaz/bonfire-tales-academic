

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0003_tbmapmarker'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbTalento',
            fields=[
                ('id_talento', models.AutoField(db_column='Id_Talento', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150)),
                ('slug', models.SlugField(db_column='Slug', help_text='Ex: guerreiro-nato (usado para links)', max_length=150, unique=True)),
                ('tipo', models.CharField(choices=[('origem', 'Origem'), ('geral', 'Geral')], db_column='Tipo', default='geral', max_length=50)),
                ('etiqueta', models.CharField(choices=[('combate', 'COMBATE'), ('conjuracao', 'CONJURAÇÃO'), ('exploracao', 'EXPLORAÇÃO'), ('hemomancia', 'HEMOMANCIA'), ('marcas', 'MARCAS'), ('masterizacao', 'MASTERIZAÇÃO'), ('sobrevivencia', 'SOBREVIVÊNCIA'), ('social', 'SOCIAL'), ('suporte', 'SUPORTE'), ('utilidade', 'UTILIDADE')], db_column='Etiqueta', default='combate', help_text='Categoria/Tag principal do talento.', max_length=50)),
                ('descricao', models.TextField(db_column='Descricao', help_text='Use Markdown para formatar os benefícios (Listas, Negrito, Títulos).')),
                ('atrib_forca', models.BooleanField(db_column='Atrib_Forca', default=False, verbose_name='+1 Força')),
                ('atrib_destreza', models.BooleanField(db_column='Atrib_Destreza', default=False, verbose_name='+1 Destreza')),
                ('atrib_constituicao', models.BooleanField(db_column='Atrib_Constituicao', default=False, verbose_name='+1 Constituição')),
                ('atrib_inteligencia', models.BooleanField(db_column='Atrib_Inteligencia', default=False, verbose_name='+1 Inteligência')),
                ('atrib_sabedoria', models.BooleanField(db_column='Atrib_Sabedoria', default=False, verbose_name='+1 Sabedoria')),
                ('atrib_carisma', models.BooleanField(db_column='Atrib_Carisma', default=False, verbose_name='+1 Carisma')),
            ],
            options={
                'verbose_name': 'Talento',
                'verbose_name_plural': 'Talentos',
                'db_table': 'TB_Talento',
            },
        ),
        migrations.AlterField(
            model_name='tbmapmarker',
            name='icone',
            field=models.CharField(choices=[('black_castle.webp', 'Black Castle'), ('blue_castle.webp', 'Blue Castle'), ('blue_city.webp', 'Blue City'), ('blue_port.webp', 'Blue Port'), ('blue_tower.webp', 'Blue Tower'), ('flat_black_beast.webp', 'Flat Black Beast'), ('flat_black_skull.webp', 'Flat Black Skull'), ('green_castle.webp', 'Green Castle'), ('green_city.webp', 'Green City'), ('grey_castle.webp', 'Grey Castle'), ('grey_church.webp', 'Grey Church'), ('grey_city.webp', 'Grey City'), ('orange_camp.webp', 'Orange Camp'), ('orange_capitol.webp', 'Orange Capitol'), ('orange_castle.webp', 'Orange Castle'), ('orange_city.webp', 'Orange City'), ('red_castle.webp', 'Red Castle'), ('red_city.webp', 'Red City'), ('red_danger.webp', 'Red Danger'), ('red_farm.webp', 'Red Farm'), ('red_mountains.webp', 'Red Mountains'), ('red_port.webp', 'Red Port'), ('red_sea.webp', 'Red Sea'), ('red_tower.webp', 'Red Tower'), ('red_village.webp', 'Red Village'), ('violet_castle.webp', 'Violet Castle'), ('violet_village.webp', 'Violet Village'), ('yellow_castle.webp', 'Yellow Castle'), ('yellow_city.webp', 'Yellow City'), ('yellow_port.webp', 'Yellow Port')], db_column='Icone', default='blue_castle.webp', max_length=50),
        ),
    ]
