from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0010_alter_tbtracoracial_nivel_requisito_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="tbtracoracial",
            name="pre_requisito",
            field=models.TextField(
                blank=True,
                db_column="PreRequisito",
                help_text="Pre-requisito para talentos raciais opcionais.",
                null=True,
            ),
        ),
    ]
