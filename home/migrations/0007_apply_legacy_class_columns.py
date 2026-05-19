from django.db import migrations


def ensure_legacy_class_tables(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        existing_tables = schema_editor.connection.introspection.table_names()
        if "TB_Classe" not in existing_tables:
            cursor.execute("""
                CREATE TABLE "TB_Classe" (
                    "Id_Classe" SERIAL PRIMARY KEY,
                    "Nome" varchar(100) NOT NULL,
                    "Slug" varchar(100) NOT NULL UNIQUE,
                    "Tagline" text NULL
                )
            """)

        if "TB_ClasseHabilidade" not in existing_tables:
            cursor.execute("""
                CREATE TABLE "TB_ClasseHabilidade" (
                    "Id_Habilidade" SERIAL PRIMARY KEY,
                    "Nome" varchar(100) NOT NULL,
                    "Descricao" text NULL,
                    "NivelAdquirido" integer NOT NULL DEFAULT 0,
                    "Id_Classe" integer NULL,
                    "Id_Subclasse" integer NULL
                )
            """)


def add_column_if_missing(schema_editor, table_name, column_name, column_type):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            [table_name],
        )
        existing_columns = {row[0] for row in cursor.fetchall()}
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

    add_column_if_missing(schema_editor, "TB_ClasseHabilidade", "TableOnly", "boolean NOT NULL DEFAULT FALSE")


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0006_classe_profile_fields_habilidade_table_only"),
    ]

    operations = [
        migrations.RunPython(add_legacy_class_columns, migrations.RunPython.noop),
    ]
