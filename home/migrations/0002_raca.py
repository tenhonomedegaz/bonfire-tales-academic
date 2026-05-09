

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbEssencia',
            fields=[
                ('id_essencia', models.AutoField(db_column='Id_Essencia', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=100)),
                ('slug', models.CharField(db_column='Slug', max_length=100, unique=True)),
                ('lore_presentation', models.TextField(blank=True, db_column='LorePresentation', null=True)),
                ('lore_roleplay', models.TextField(blank=True, db_column='LoreRoleplay', null=True)),
                ('lore_society', models.TextField(blank=True, db_column='LoreSociety', null=True)),
            ],
            options={
                'db_table': 'TB_Essencia',
            },
        ),
        migrations.CreateModel(
            name='TbRaca',
            fields=[
                ('id_raca', models.AutoField(db_column='Id_Raca', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=100)),
                ('slug', models.CharField(db_column='Slug', max_length=100, unique=True)),
                ('tagline', models.CharField(blank=True, db_column='Tagline', max_length=255, null=True)),
                ('lore_presentation', models.TextField(blank=True, db_column='LorePresentation', null=True)),
                ('lore_roleplay', models.TextField(blank=True, db_column='LoreRoleplay', null=True)),
                ('lore_society', models.TextField(blank=True, db_column='LoreSociety', null=True)),
                ('permite_essencia', models.BooleanField(db_column='PermiteEssencia', default=True)),
            ],
            options={
                'db_table': 'TB_Raca',
            },
        ),
        migrations.RemoveField(
            model_name='linhagemtraco',
            name='linhagem',
        ),
        migrations.RemoveField(
            model_name='racatraco',
            name='raca',
        ),
        migrations.CreateModel(
            name='TbLinhagem',
            fields=[
                ('id_linhagem', models.AutoField(db_column='Id_Linhagem', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=100)),
                ('slug', models.CharField(db_column='Slug', max_length=100, unique=True)),
                ('lore_presentation', models.TextField(blank=True, db_column='LorePresentation', null=True)),
                ('lore_roleplay', models.TextField(blank=True, db_column='LoreRoleplay', null=True)),
                ('lore_society', models.TextField(blank=True, db_column='LoreSociety', null=True)),
                ('descricao', models.TextField(blank=True, db_column='Descricao', null=True)),
                ('id_raca', models.ForeignKey(db_column='Id_Raca', on_delete=django.db.models.deletion.CASCADE, related_name='linhagens', to='home.tbraca')),
            ],
            options={
                'db_table': 'TB_Linhagem',
            },
        ),
        migrations.CreateModel(
            name='TbTracoracial',
            fields=[
                ('id_traco', models.AutoField(db_column='Id_Traco', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150)),
                ('descricao', models.TextField(db_column='Descricao')),
                ('nivel_requisito', models.IntegerField(db_column='NivelRequisito', default=1)),
                ('id_essencia', models.ForeignKey(blank=True, db_column='Id_Essencia', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tracos', to='home.tbessencia')),
                ('id_linhagem', models.ForeignKey(blank=True, db_column='Id_Linhagem', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tracos_linhagem', to='home.tblinhagem')),
                ('id_raca', models.ForeignKey(blank=True, db_column='Id_Raca', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='tracos', to='home.tbraca')),
            ],
            options={
                'db_table': 'TB_TracoRacial',
            },
        ),
        migrations.DeleteModel(
            name='Linhagem',
        ),
        migrations.DeleteModel(
            name='LinhagemTraco',
        ),
        migrations.DeleteModel(
            name='Raca',
        ),
        migrations.DeleteModel(
            name='RacaTraco',
        ),
    ]
