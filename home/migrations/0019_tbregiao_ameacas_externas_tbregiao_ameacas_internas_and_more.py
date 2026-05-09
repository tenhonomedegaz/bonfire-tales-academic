

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0018_tbterritorio'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbregiao',
            name='ameacas_externas',
            field=models.IntegerField(db_column='AmeacasExternas', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='ameacas_internas',
            field=models.IntegerField(db_column='AmeacasInternas', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='densidade_populacional',
            field=models.IntegerField(db_column='DensidadePopulacional', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='desenvolvimento_tecnologico',
            field=models.IntegerField(db_column='DesenvolvimentoTecnologico', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='diversidade_criaturas',
            field=models.IntegerField(db_column='DiversidadeCriaturas', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='estabilidade_politica_interna',
            field=models.IntegerField(db_column='EstabilidadePoliticaInterna', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='manipulacao_trama',
            field=models.IntegerField(db_column='ManipulacaoTrama', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='movimentacoes_economicas',
            field=models.IntegerField(db_column='MovimentacoesEconomicas', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='nivel_periculosidade',
            field=models.IntegerField(db_column='NivelPericulosidade', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='poder_militar',
            field=models.IntegerField(db_column='PoderMilitar', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='recursos_magicos',
            field=models.IntegerField(db_column='RecursosMagicos', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='recursos_naturais',
            field=models.IntegerField(db_column='RecursosNaturais', default=0),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='tolerancia_estrangeiros',
            field=models.IntegerField(db_column='ToleranciaEstrangeiros', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='ameacas_externas',
            field=models.IntegerField(db_column='AmeacasExternas', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='desenvolvimento_tecnologico',
            field=models.IntegerField(db_column='DesenvolvimentoTecnologico', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='diplomacia',
            field=models.IntegerField(db_column='Diplomacia', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='estabilidade_politica_interna',
            field=models.IntegerField(db_column='EstabilidadePoliticaInterna', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='manipulacao_trama',
            field=models.IntegerField(db_column='ManipulacaoTrama', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='poder_militar',
            field=models.IntegerField(db_column='PoderMilitar', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='riqueza_monetaria',
            field=models.IntegerField(db_column='RiquezaMonetaria', default=0),
        ),
        migrations.AddField(
            model_name='tbterritorio',
            name='riqueza_natural',
            field=models.IntegerField(db_column='RiquezaNatural', default=0),
        ),
        migrations.AlterField(
            model_name='tbmapmarker',
            name='categoria',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('fortaleza', 'Fortaleza'), ('conglomerado_vilas', 'Conglomerado de Vilas'), ('cidade_portuaria', 'Cidade Portuária'), ('area_selvagem', 'Área Selvagem'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='Categoria', default='cidade', max_length=50),
        ),
        migrations.AlterField(
            model_name='tbmapmarker',
            name='pin_icon',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('fortaleza', 'Fortaleza'), ('conglomerado_vilas', 'Conglomerado de Vilas'), ('cidade_portuaria', 'Cidade Portuária'), ('area_selvagem', 'Área Selvagem'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='PinIcon', default='cidade', max_length=50),
        ),
        migrations.AlterField(
            model_name='tbregiao',
            name='categoria',
            field=models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('fortaleza', 'Fortaleza'), ('conglomerado_vilas', 'Conglomerado de Vilas'), ('cidade_portuaria', 'Cidade Portuária'), ('area_selvagem', 'Área Selvagem'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='Categoria', default='cidade', max_length=50),
        ),
    ]
