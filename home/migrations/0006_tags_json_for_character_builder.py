# Generated manually for BonfireSite.

from django.conf import settings
from django.db import migrations, models


def add_spell_tags_json(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    table = settings.SITE_POSTGRES_TABLES.get('spells', 'spells')
    schema_editor.execute(
        f"ALTER TABLE IF EXISTS {schema_editor.quote_name(table)} "
        'ADD COLUMN IF NOT EXISTS "TagsJSON" jsonb NOT NULL DEFAULT \'[]\'::jsonb'
    )


def remove_spell_tags_json(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    table = settings.SITE_POSTGRES_TABLES.get('spells', 'spells')
    schema_editor.execute(
        f"ALTER TABLE IF EXISTS {schema_editor.quote_name(table)} "
        'DROP COLUMN IF EXISTS "TagsJSON"'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0005_tbclassehabilidade_tags_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbtracoracial',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
        migrations.AddField(
            model_name='tbopcaojogo',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
        migrations.AddField(
            model_name='tbtalento',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
        migrations.AddField(
            model_name='tbitemmundano',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
        migrations.AddField(
            model_name='tbitemmagico',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
        migrations.RunPython(add_spell_tags_json, remove_spell_tags_json),
    ]
