from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0007_apply_legacy_class_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="tbtracoracial",
            name="talento_racial",
            field=models.BooleanField(
                db_column="TalentoRacial",
                default=False,
                help_text="Marca tracos opcionais de raca que podem ser escolhidos como talentos raciais.",
            ),
        ),
    ]
