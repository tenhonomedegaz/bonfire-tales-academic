from django.db import migrations


def add_column_if_missing(schema_editor, table_name, column_name, column_type):
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            row[1]
            for row in cursor.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        }
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')


def add_legacy_racial_trait_prerequisite(apps, schema_editor):
    add_column_if_missing(schema_editor, "TB_TracoRacial", "PreRequisito", "TEXT NULL")


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0011_tbtracoracial_pre_requisito"),
    ]

    operations = [
        migrations.RunPython(add_legacy_racial_trait_prerequisite, migrations.RunPython.noop),
    ]
