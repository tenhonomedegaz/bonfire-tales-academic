from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0112_hunter_mutagens')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='regularization',
        field=models.JSONField(default=dict))]
