

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='TbAcessoopcao',
            fields=[
                ('id_acessoopcao', models.AutoField(db_column='Id_AcessoOpcao', primary_key=True, serialize=False)),
            ],
            options={
                'db_table': 'TB_AcessoOpcao',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TbClasse',
            fields=[
                ('id_classe', models.AutoField(db_column='Id_Classe', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome')),
                ('slug', models.CharField(db_column='Slug', unique=True)),
                ('tagline', models.CharField(blank=True, db_column='Tagline', null=True)),
            ],
            options={
                'db_table': 'TB_Classe',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TbClassehabilidade',
            fields=[
                ('id_habilidade', models.AutoField(db_column='Id_Habilidade', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome')),
                ('descricao', models.TextField(db_column='Descricao')),
                ('niveladquirido', models.IntegerField(db_column='NivelAdquirido')),
            ],
            options={
                'db_table': 'TB_ClasseHabilidade',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TbOpcaojogo',
            fields=[
                ('id_opcao', models.AutoField(db_column='Id_Opcao', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome')),
                ('slug', models.CharField(db_column='Slug', unique=True)),
                ('tipo', models.CharField(db_column='Tipo')),
                ('descricao', models.TextField(blank=True, db_column='Descricao', null=True)),
            ],
            options={
                'db_table': 'TB_OpcaoJogo',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TbRecursoclasse',
            fields=[
                ('id_recurso', models.AutoField(db_column='Id_Recurso', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome')),
                ('slug', models.CharField(db_column='Slug')),
                ('nivel', models.IntegerField(db_column='Nivel')),
                ('valor', models.CharField(blank=True, db_column='Valor', null=True)),
            ],
            options={
                'db_table': 'TB_RecursoClasse',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='TbSubclasse',
            fields=[
                ('id_subclasse', models.AutoField(db_column='Id_Subclasse', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome')),
                ('slug', models.CharField(db_column='Slug')),
                ('tagline', models.CharField(blank=True, db_column='Tagline', null=True)),
            ],
            options={
                'db_table': 'TB_Subclasse',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='Linhagem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('descricao', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Raca',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('slug', models.SlugField(unique=True)),
                ('tipo', models.CharField(max_length=50)),
                ('tagline', models.CharField(blank=True, max_length=255, null=True)),
                ('creature_type', models.CharField(blank=True, max_length=50, null=True)),
                ('size', models.CharField(blank=True, max_length=100, null=True)),
                ('speed', models.CharField(blank=True, max_length=50, null=True)),
                ('lifespan', models.CharField(blank=True, max_length=50, null=True)),
                ('lore_presentation', models.TextField(blank=True, null=True)),
                ('lore_roleplay', models.TextField(blank=True, null=True)),
                ('lore_society', models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='LinhagemTraco',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('texto', models.TextField()),
                ('bullets', models.JSONField(blank=True, null=True)),
                ('linhagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracos', to='home.linhagem')),
            ],
        ),
        migrations.AddField(
            model_name='linhagem',
            name='raca',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='linhagens', to='home.raca'),
        ),
        migrations.CreateModel(
            name='RacaTraco',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100)),
                ('texto', models.TextField()),
                ('bullets', models.JSONField(blank=True, null=True)),
                ('raca', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracos_base', to='home.raca')),
            ],
        ),
    ]
