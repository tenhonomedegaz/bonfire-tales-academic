

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0014_remove_tbmapmarker_icone'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbRegiao',
            fields=[
                ('id_regiao', models.AutoField(db_column='Id_Regiao', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=200)),
                ('slug', models.SlugField(db_column='Slug', max_length=200, unique=True)),
                ('lore_markdown', models.TextField(blank=True, db_column='LoreMarkdown', help_text='Conteudo completo de lore da regiao em Markdown.', null=True)),
                ('descricao_breve', models.TextField(blank=True, db_column='DescricaoBreve', null=True)),
                ('territorio', models.CharField(blank=True, db_column='Territorio', max_length=150, null=True)),
                ('categoria', models.CharField(choices=[('capital', 'Capital'), ('cidade', 'Cidade'), ('vila', 'Vila'), ('castelo', 'Castelo'), ('ruina', 'Ruina'), ('torre', 'Torre'), ('porto', 'Porto'), ('dungeon', 'Dungeon'), ('floresta', 'Floresta'), ('montanha', 'Montanha'), ('portal', 'Portal'), ('santuario', 'Santuario'), ('faccao', 'Faccao'), ('evento', 'Evento'), ('segredo', 'Segredo'), ('templo', 'Templo'), ('area_perigosa', 'Area Perigosa')], db_column='Categoria', default='cidade', max_length=50)),
                ('faccao_dominante', models.CharField(blank=True, db_column='FaccaoDominante', max_length=150, null=True)),
                ('tecnologia', models.CharField(blank=True, db_column='Tecnologia', max_length=100, null=True)),
                ('magia', models.CharField(blank=True, db_column='Magia', max_length=100, null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', help_text='URL ou caminho static da imagem de capa.', max_length=500, null=True)),
                ('token_color', models.CharField(choices=[('red', 'Vermelho'), ('blue', 'Azul'), ('green', 'Verde'), ('yellow', 'Amarelo'), ('orange', 'Laranja'), ('violet', 'Violeta'), ('gray', 'Cinza'), ('black', 'Preto')], db_column='TokenColor', default='blue', max_length=30)),
            ],
            options={
                'verbose_name': 'Região',
                'verbose_name_plural': 'Regiões',
                'db_table': 'TB_Regiao',
            },
        ),
    ]
