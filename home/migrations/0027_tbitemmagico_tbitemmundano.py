

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0026_regiao_tags_mapa_cronica_multi_text'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbItemMagico',
            fields=[
                ('id_item', models.AutoField(db_column='Id_Item', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150)),
                ('slug', models.SlugField(db_column='Slug', max_length=150, unique=True)),
                ('raridade', models.CharField(choices=[('comum', 'Comum'), ('incomum', 'Incomum'), ('raro', 'Raro'), ('muito_raro', 'Muito Raro'), ('lendario', 'Lendário'), ('artefato', 'Artefato')], db_column='Raridade', default='incomum', max_length=50)),
                ('requer_sintonizacao', models.BooleanField(db_column='RequerSintonizacao', default=False)),
                ('detalhes_sintonizacao', models.CharField(blank=True, db_column='DetalhesSintonizacao', help_text='Ex: por um mago', max_length=150, null=True)),
                ('slot', models.CharField(choices=[('cabeca', 'Cabeça'), ('face_olhos', 'Face/Olhos'), ('pescoco', 'Pescoço'), ('costas', 'Costas'), ('torso', 'Torso'), ('maos', 'Mãos'), ('dedos', 'Dedos'), ('cintura', 'Cintura'), ('pes', 'Pés'), ('objeto', 'Objeto'), ('item_menor', 'Item Menor')], db_column='Slot', default='objeto', max_length=50)),
                ('tipo', models.CharField(blank=True, db_column='Tipo', help_text='Ex: Espada longa, Poção, Anel', max_length=100, null=True)),
                ('descricao_markdown', models.TextField(blank=True, db_column='DescricaoMarkdown', null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True)),
            ],
            options={
                'verbose_name': 'Item Mágico',
                'verbose_name_plural': 'Itens Mágicos',
                'db_table': 'TB_ItemMagico',
            },
        ),
        migrations.CreateModel(
            name='TbItemMundano',
            fields=[
                ('id_item', models.AutoField(db_column='Id_Item', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=150)),
                ('slug', models.SlugField(db_column='Slug', max_length=150, unique=True)),
                ('categoria', models.CharField(choices=[('arma', 'Arma'), ('armadura', 'Armadura'), ('ferramenta', 'Ferramenta'), ('pacote', 'Pacote'), ('equipamento_aventura', 'Equipamento de Aventura')], db_column='Categoria', default='equipamento_aventura', max_length=50)),
                ('subcategoria', models.CharField(blank=True, db_column='Subcategoria', help_text='Ex: arma_simples, escudo, ferramenta_artesao', max_length=100, null=True)),
                ('peso', models.FloatField(blank=True, db_column='Peso', help_text='Peso em kg ou lbs', null=True)),
                ('preco', models.CharField(blank=True, db_column='Preco', help_text='Ex: 5 PO', max_length=50, null=True)),
                ('dano', models.CharField(blank=True, db_column='Dano', help_text='Ex: 1d8 cortante', max_length=50, null=True)),
                ('propriedades', models.CharField(blank=True, db_column='Propriedades', help_text='Ex: Acuidade, Leve', max_length=200, null=True)),
                ('maestria', models.CharField(blank=True, db_column='Maestria', help_text='Opção adicional de maestria', max_length=100, null=True)),
                ('ca', models.CharField(blank=True, db_column='CA', help_text='Ex: 14 + mod Des (max 2)', max_length=50, null=True)),
                ('forca_minima', models.IntegerField(blank=True, db_column='ForcaMinima', help_text='Força mínima para usar', null=True)),
                ('furtividade_desvantagem', models.BooleanField(db_column='FurtividadeDesvantagem', default=False)),
                ('descricao_markdown', models.TextField(blank=True, db_column='DescricaoMarkdown', null=True)),
                ('imagem_url', models.CharField(blank=True, db_column='ImagemUrl', max_length=500, null=True)),
            ],
            options={
                'verbose_name': 'Item Mundano',
                'verbose_name_plural': 'Itens Mundanos',
                'db_table': 'TB_ItemMundano',
            },
        ),
    ]
