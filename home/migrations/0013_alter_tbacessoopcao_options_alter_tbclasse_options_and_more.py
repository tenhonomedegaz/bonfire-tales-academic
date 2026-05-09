

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0012_apply_legacy_racial_trait_prerequisite'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tbacessoopcao',
            options={'managed': False, 'verbose_name': 'Acesso de Opção', 'verbose_name_plural': 'Acessos de Opções'},
        ),
        migrations.AlterModelOptions(
            name='tbclasse',
            options={'managed': False, 'verbose_name': 'Classe', 'verbose_name_plural': 'Classes'},
        ),
        migrations.AlterModelOptions(
            name='tbclassehabilidade',
            options={'managed': False, 'verbose_name': 'Habilidade de Classe', 'verbose_name_plural': 'Habilidades de Classe'},
        ),
        migrations.AlterModelOptions(
            name='tbessencia',
            options={'verbose_name': 'Essência', 'verbose_name_plural': 'Essências'},
        ),
        migrations.AlterModelOptions(
            name='tblinhagem',
            options={'verbose_name': 'Linhagem', 'verbose_name_plural': 'Linhagens'},
        ),
        migrations.AlterModelOptions(
            name='tbmapmarker',
            options={'verbose_name': 'Marcador do Mapa', 'verbose_name_plural': 'Marcadores do Mapa'},
        ),
        migrations.AlterModelOptions(
            name='tbopcaojogo',
            options={'managed': False, 'verbose_name': 'Opção de Jogo', 'verbose_name_plural': 'Opções de Jogo'},
        ),
        migrations.AlterModelOptions(
            name='tbraca',
            options={'verbose_name': 'Raça', 'verbose_name_plural': 'Raças'},
        ),
        migrations.AlterModelOptions(
            name='tbrecursoclasse',
            options={'managed': False, 'verbose_name': 'Recurso de Classe', 'verbose_name_plural': 'Recursos de Classe'},
        ),
        migrations.AlterModelOptions(
            name='tbsubclasse',
            options={'managed': False, 'verbose_name': 'Subclasse', 'verbose_name_plural': 'Subclasses'},
        ),
        migrations.AlterModelOptions(
            name='tbtracoracial',
            options={'verbose_name': 'Traço Racial', 'verbose_name_plural': 'Traços Raciais'},
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='categoria',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='Categoria', default='cidade', max_length=50),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='descricao_breve',
            field=models.TextField(blank=True, db_column='DescricaoBreve', null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='faccao_dominante',
            field=models.CharField(blank=True, db_column='FaccaoDominante', max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='imagem_url',
            field=models.CharField(blank=True, db_column='ImagemUrl', help_text='URL ou caminho static da imagem de fundo do card.', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='lore_url',
            field=models.CharField(blank=True, db_column='LoreUrl', help_text='Link para a pagina de lore completa.', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='magia',
            field=models.CharField(blank=True, db_column='Magia', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='pin_icon',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='PinIcon', default='cidade', max_length=50),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='tecnologia',
            field=models.CharField(blank=True, db_column='Tecnologia', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='territorio',
            field=models.CharField(blank=True, db_column='Territorio', max_length=150, null=True),
        ),
        migrations.AddField(
            model_name='tbmapmarker',
            name='token_color',
            field=models.CharField(choices=[('red', 'Vermelho'), ('blue', 'Azul'), ('green', 'Verde'), ('yellow', 'Amarelo'), ('orange', 'Laranja'), ('violet', 'Violeta'), ('gray', 'Cinza'), ('black', 'Preto')], db_column='TokenColor', default='blue', max_length=30),
        ),
    ]
