from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0113_hunter_regularization')]

    operations = [
        migrations.AddField(
            model_name='tbcronica',
            name='revisao_edicao',
            field=models.JSONField(blank=True, db_column='RevisaoEdicao', default=dict),
        ),
    ]
