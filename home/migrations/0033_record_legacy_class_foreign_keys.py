import django.db.models.deletion
from django.db import migrations, models


def add_column_if_missing(schema_editor, table_name, column_name, column_type):
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            row[1]
            for row in cursor.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        }
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')


def ensure_legacy_foreign_key_columns(apps, schema_editor):
    existing_tables = schema_editor.connection.introspection.table_names()
    if "TB_Subclasse" in existing_tables:
        add_column_if_missing(schema_editor, "TB_Subclasse", "Id_Classe", "integer NULL")
    if "TB_ClasseHabilidade" in existing_tables:
        add_column_if_missing(schema_editor, "TB_ClasseHabilidade", "Id_Classe", "integer NULL")
        add_column_if_missing(schema_editor, "TB_ClasseHabilidade", "Id_Subclasse", "integer NULL")
    if "TB_RecursoClasse" in existing_tables:
        add_column_if_missing(schema_editor, "TB_RecursoClasse", "Id_Classe", "integer NULL")
        add_column_if_missing(schema_editor, "TB_RecursoClasse", "Id_Subclasse", "integer NULL")


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0032_ensure_class_tables_exist"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_legacy_foreign_key_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="tbclassehabilidade",
                    name="id_classe",
                    field=models.ForeignKey(
                        db_column="Id_Classe",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="home.tbclasse",
                    ),
                ),
                migrations.AddField(
                    model_name="tbclassehabilidade",
                    name="id_subclasse",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="Id_Subclasse",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="home.tbsubclasse",
                    ),
                ),
                migrations.AddField(
                    model_name="tbrecursoclasse",
                    name="id_classe",
                    field=models.ForeignKey(
                        db_column="Id_Classe",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="home.tbclasse",
                    ),
                ),
                migrations.AddField(
                    model_name="tbrecursoclasse",
                    name="id_subclasse",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="Id_Subclasse",
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="home.tbsubclasse",
                    ),
                ),
                migrations.AddField(
                    model_name="tbsubclasse",
                    name="id_classe",
                    field=models.ForeignKey(
                        db_column="Id_Classe",
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to="home.tbclasse",
                    ),
                ),
            ],
        ),
    ]
