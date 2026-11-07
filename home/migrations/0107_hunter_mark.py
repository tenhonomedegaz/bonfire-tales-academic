from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0106_hunter_preparation')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='mark', field=models.JSONField(default=dict))]
