from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0162_progression_milestone_choice')]

    operations = [
        migrations.AlterField(
            model_name='tbpersonagem',
            name='publico',
            field=models.BooleanField(db_column='Publico', default=True),
        ),
    ]
