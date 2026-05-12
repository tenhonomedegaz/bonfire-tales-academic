from django.db import migrations


def table_exists(schema_editor, table_name):
    return table_name in schema_editor.connection.introspection.table_names()


def ensure_legacy_class_tables(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if not table_exists(schema_editor, "TB_Classe"):
            cursor.execute("""
                CREATE TABLE "TB_Classe" (
                    "Id_Classe" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "Nome" varchar(100) NOT NULL,
                    "Slug" varchar(100) NOT NULL UNIQUE,
                    "Tagline" text NULL
                )
            """)

        if not table_exists(schema_editor, "TB_ClasseHabilidade"):
            cursor.execute("""
                CREATE TABLE "TB_ClasseHabilidade" (
                    "Id_Habilidade" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    "Nome" varchar(100) NOT NULL,
                    "Descricao" text NULL,
                    "NivelAdquirido" integer NOT NULL DEFAULT 0,
                    "Id_Classe" integer NULL,
                    "Id_Subclasse" integer NULL
                )
            """)


def add_column_if_missing(schema_editor, table_name, column_name, column_type):
    with schema_editor.connection.cursor() as cursor:
        existing_columns = {
            row[1]
            for row in cursor.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        }
        if column_name not in existing_columns:
            cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')


def add_legacy_class_columns(apps, schema_editor):
    ensure_legacy_class_tables(schema_editor)

    class_text_columns = [
        "AtributoPrincipal",
        "DadoVida",
        "PVNivel1",
        "PVPORNivel",
        "Resistencias",
        "Pericias",
        "Armas",
        "Ferramentas",
        "Armaduras",
        "Equipamento",
        "MulticlassRequisitos",
        "MulticlassPericias",
        "MulticlassFerramentas",
        "MulticlassArmaduras",
    ]
    for column_name in class_text_columns:
        add_column_if_missing(schema_editor, "TB_Classe", column_name, "TEXT NULL")

    add_column_if_missing(schema_editor, "TB_ClasseHabilidade", "TableOnly", "bool NOT NULL DEFAULT 0")


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0006_classe_profile_fields_habilidade_table_only"),
    ]

    operations = [
        migrations.RunPython(add_legacy_class_columns, migrations.RunPython.noop),
    ]
