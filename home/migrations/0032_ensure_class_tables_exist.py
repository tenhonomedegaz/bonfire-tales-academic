"""
Safety migration: ensures TB_Classe, TB_ClasseHabilidade, TB_RecursoClasse, TB_Subclasse
tables exist. These were originally managed=False (created outside Django) so Django
never had a CreateModel migration for them. If the database is recreated from scratch,
migrate would fail because these tables don't exist and Django doesn't know to create them.
"""
from django.db import migrations, models
import django.db.models.deletion


def ensure_tables_exist(apps, schema_editor):
    """Create tables only if they don't already exist."""
    connection = schema_editor.connection
    existing_tables = connection.introspection.table_names()

    cursor = connection.cursor()

    autoincrement = 'SERIAL PRIMARY KEY'
    boolean_false = 'FALSE'

    if 'TB_Classe' not in existing_tables:
        cursor.execute(f"""
            CREATE TABLE "TB_Classe" (
                "Id_Classe" {autoincrement},
                "Nome" varchar(100) NOT NULL,
                "Slug" varchar(100) NOT NULL UNIQUE,
                "Tagline" text NULL,
                "AtributoPrincipal" varchar(100) NULL,
                "DadoVida" varchar(20) NULL,
                "PVNivel1" varchar(100) NULL,
                "PVPORNivel" varchar(100) NULL,
                "Resistencias" varchar(200) NULL,
                "Pericias" text NULL,
                "Armas" text NULL,
                "Ferramentas" text NULL,
                "Armaduras" text NULL,
                "Equipamento" text NULL,
                "MulticlassRequisitos" text NULL,
                "MulticlassPericias" text NULL,
                "MulticlassFerramentas" text NULL,
                "MulticlassArmaduras" text NULL
            )
        """)

    if 'TB_Subclasse' not in existing_tables:
        cursor.execute(f"""
            CREATE TABLE "TB_Subclasse" (
                "Id_Subclasse" {autoincrement},
                "Nome" varchar(100) NOT NULL,
                "Slug" varchar(100) NOT NULL UNIQUE,
                "Tagline" text NULL,
                "Id_Classe" integer NULL REFERENCES "TB_Classe" ("Id_Classe") DEFERRABLE INITIALLY DEFERRED
            )
        """)

    if 'TB_ClasseHabilidade' not in existing_tables:
        cursor.execute(f"""
            CREATE TABLE "TB_ClasseHabilidade" (
                "Id_Habilidade" {autoincrement},
                "Nome" varchar(100) NOT NULL,
                "Descricao" text NULL,
                "NivelAdquirido" integer NOT NULL DEFAULT 0,
                "TableOnly" boolean NOT NULL DEFAULT {boolean_false},
                "Id_Classe" integer NULL REFERENCES "TB_Classe" ("Id_Classe") DEFERRABLE INITIALLY DEFERRED,
                "Id_Subclasse" integer NULL REFERENCES "TB_Subclasse" ("Id_Subclasse") DEFERRABLE INITIALLY DEFERRED
            )
        """)

    if 'TB_RecursoClasse' not in existing_tables:
        cursor.execute(f"""
            CREATE TABLE "TB_RecursoClasse" (
                "Id_Recurso" {autoincrement},
                "Nome" varchar(100) NOT NULL,
                "Slug" varchar(100) NOT NULL,
                "Nivel" integer NOT NULL DEFAULT 0,
                "Valor" varchar(100) NULL,
                "Id_Classe" integer NULL REFERENCES "TB_Classe" ("Id_Classe") DEFERRABLE INITIALLY DEFERRED,
                "Id_Subclasse" integer NULL REFERENCES "TB_Subclasse" ("Id_Subclasse") DEFERRABLE INITIALLY DEFERRED
            )
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0031_alter_tbclasse_options_and_more'),
    ]

    operations = [
        migrations.RunPython(ensure_tables_exist, migrations.RunPython.noop),
    ]
