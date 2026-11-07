from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0169_bot_mission_reviews')]
    operations = [migrations.AddField(
        model_name='tbperfilmestre', name='candidatura_json',
        field=models.JSONField(blank=True, default=dict))]
