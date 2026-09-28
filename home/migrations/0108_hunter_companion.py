from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0107_hunter_mark')]
    operations = [migrations.AddField(
        model_name='tbpersonagemcacador', name='companion',
        field=models.JSONField(default=dict))]
