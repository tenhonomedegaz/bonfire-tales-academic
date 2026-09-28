from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0109_hunter_awakening')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='exorcist',
        field=models.JSONField(default=dict))]
