from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0111_hunter_traveler')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='mutagens',
        field=models.JSONField(default=dict))]
