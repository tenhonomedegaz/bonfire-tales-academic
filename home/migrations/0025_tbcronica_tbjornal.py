

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0024_tbterritorio_cor_hex_alter_tbacessoopcao_id_opcao'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TbCronica',
            fields=[
                ('id_cronica', models.AutoField(db_column='Id_Cronica', primary_key=True, serialize=False)),
                ('titulo', models.CharField(db_column='Titulo', max_length=200)),
                ('slug', models.SlugField(db_column='Slug', max_length=220, unique=True)),
                ('conteudo_markdown', models.TextField(db_column='ConteudoMarkdown')),
                ('resumo', models.CharField(blank=True, db_column='Resumo', max_length=300, null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True)),
                ('personagem_nome', models.CharField(blank=True, db_column='PersonagemNome', help_text='Nome do personagem narrador.', max_length=150, null=True)),
                ('territorio', models.CharField(blank=True, db_column='Territorio', help_text='Território onde a crônica se passa.', max_length=150, null=True)),
                ('regiao', models.CharField(blank=True, db_column='Regiao', help_text='Região específica onde a crônica se passa.', max_length=200, null=True)),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('aprovada', 'Aprovada'), ('reprovada', 'Reprovada')], db_column='Status', default='pendente', max_length=20)),
                ('feedback_staff', models.TextField(blank=True, db_column='FeedbackStaff', help_text='Feedback do staff na revisão.', null=True)),
                ('data_submissao', models.DateTimeField(auto_now_add=True, db_column='DataSubmissao')),
                ('data_revisao', models.DateTimeField(blank=True, db_column='DataRevisao', null=True)),
                ('autor', models.ForeignKey(db_column='Autor', on_delete=django.db.models.deletion.CASCADE, related_name='cronicas', to=settings.AUTH_USER_MODEL)),
                ('revisado_por', models.ForeignKey(blank=True, db_column='RevisadoPor', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cronicas_revisadas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Crônica',
                'verbose_name_plural': 'Crônicas',
                'db_table': 'TB_Cronica',
                'ordering': ['-data_submissao'],
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='TbJornal',
            fields=[
                ('id_jornal', models.AutoField(db_column='Id_Jornal', primary_key=True, serialize=False)),
                ('titulo', models.CharField(db_column='Titulo', max_length=200)),
                ('slug', models.SlugField(db_column='Slug', max_length=220, unique=True)),
                ('conteudo_markdown', models.TextField(blank=True, db_column='ConteudoMarkdown', null=True)),
                ('resumo', models.CharField(blank=True, db_column='Resumo', max_length=300, null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True)),
                ('data_publicacao', models.DateTimeField(auto_now_add=True, db_column='DataPublicacao')),
                ('data_edicao', models.DateTimeField(auto_now=True, db_column='DataEdicao')),
                ('destaque', models.BooleanField(db_column='Destaque', default=False)),
                ('autor', models.ForeignKey(blank=True, db_column='Autor', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='jornais', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Artigo de Jornal',
                'verbose_name_plural': 'Artigos de Jornal',
                'db_table': 'TB_Jornal',
                'ordering': ['-data_publicacao'],
                'managed': True,
            },
        ),
    ]
