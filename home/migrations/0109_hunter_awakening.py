from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0108_hunter_companion')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='awakening',
        field=models.JSONField(default=dict))]
