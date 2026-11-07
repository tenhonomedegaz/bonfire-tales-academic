from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0110_hunter_exorcist')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='traveler',
        field=models.JSONField(default=dict))]
