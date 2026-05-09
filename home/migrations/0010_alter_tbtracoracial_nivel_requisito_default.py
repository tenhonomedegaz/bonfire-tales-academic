from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0009_apply_legacy_racial_trait_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tbtracoracial",
            name="nivel_requisito",
            field=models.IntegerField(db_column="NivelRequisito", default=0),
        ),
    ]
