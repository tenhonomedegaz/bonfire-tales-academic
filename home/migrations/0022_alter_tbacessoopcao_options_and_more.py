

from django.db import migrations, models


def ensure_legacy_option_tables(apps, schema_editor):
    existing_tables = schema_editor.connection.introspection.table_names()
    with schema_editor.connection.cursor() as cursor:
        if "TB_OpcaoJogo" not in existing_tables:
            cursor.execute("""
                CREATE TABLE "TB_OpcaoJogo" (
                    "Id_Opcao" SERIAL PRIMARY KEY,
                    "Nome" varchar(100) NOT NULL,
                    "Slug" varchar(100) NOT NULL UNIQUE,
                    "Tipo" varchar(100) NOT NULL,
                    "Descricao" text NULL
                )
            """)

        if "TB_AcessoOpcao" not in existing_tables:
            cursor.execute("""
                CREATE TABLE "TB_AcessoOpcao" (
                    "Id_AcessoOpcao" SERIAL PRIMARY KEY
                )
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0021_tbterritorio_coordenadas_poligono'),
    ]

    operations = [
        migrations.RunPython(ensure_legacy_option_tables, migrations.RunPython.noop),
        migrations.AlterModelOptions(
            name='tbacessoopcao',
            options={'managed': True, 'verbose_name': 'Acesso de Opção', 'verbose_name_plural': 'Acessos de Opções'},
        ),
        migrations.AlterModelOptions(
            name='tbopcaojogo',
            options={'managed': True, 'verbose_name': 'Opção de Jogo', 'verbose_name_plural': 'Opções de Jogo'},
        ),
        migrations.AddField(
            model_name='tbacessoopcao',
            name='nivel_recebimento',
            field=models.IntegerField(db_column='NivelRecebimento', default=1),
        ),
        migrations.AddField(
            model_name='tbopcaojogo',
            name='pre_requisito',
            field=models.TextField(blank=True, db_column='PreRequisito', null=True, help_text='Pré-requisitos da opção.'),
        ),
    ]
