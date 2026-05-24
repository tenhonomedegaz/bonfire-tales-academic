# Generated manually for BonfireSite.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0004_tbclasse_multiclass_armas'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbclassehabilidade',
            name='tags_json',
            field=models.JSONField(blank=True, db_column='TagsJSON', default=list, help_text='Tags estruturadas usadas pelo criador de personagem.'),
        ),
    ]
