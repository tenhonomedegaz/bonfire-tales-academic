from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0058_tbmapdesenho'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbOrganizacao',
            fields=[
                ('id_organizacao', models.AutoField(db_column='Id_Organizacao', primary_key=True, serialize=False)),
                ('nome', models.CharField(db_column='Nome', max_length=200)),
                ('slug', models.SlugField(db_column='Slug', max_length=220, unique=True)),
                ('tipo', models.CharField(db_column='Tipo', default='Organizacao', max_length=120)),
                ('sede', models.CharField(blank=True, db_column='Sede', max_length=220, null=True)),
                ('regioes', models.JSONField(blank=True, db_column='Regioes', default=list, null=True)),
                ('territorios', models.JSONField(blank=True, db_column='Territorios', default=list, null=True)),
                ('lideranca', models.TextField(blank=True, db_column='Lideranca', null=True)),
                ('aliados', models.JSONField(blank=True, db_column='Aliados', default=list, null=True)),
                ('inimigos', models.JSONField(blank=True, db_column='Inimigos', default=list, null=True)),
                ('tags', models.JSONField(blank=True, db_column='Tags', default=list, null=True)),
                ('descricao', models.TextField(blank=True, db_column='Descricao', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_column='CreatedAt')),
                ('updated_at', models.DateTimeField(auto_now=True, db_column='UpdatedAt')),
            ],
            options={
                'verbose_name': 'Organizacao',
                'verbose_name_plural': 'Organizacoes',
                'db_table': 'organizations',
            },
        ),
    ]
