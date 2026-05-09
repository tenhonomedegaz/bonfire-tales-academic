

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0016_seed_regioes_from_markers'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbregiao',
            name='brasao_url',
            field=models.CharField(blank=True, db_column='BrasaoUrl', help_text='URL ou caminho static da imagem do brasão.', max_length=500, null=True),
        ),
    ]
