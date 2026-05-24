# Generated manually for BonfireSite.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0003_botcharacterlog_botdedicatedrank_botkeyvaluestore_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbclasse',
            name='multiclass_armas',
            field=models.TextField(blank=True, db_column='MulticlassArmas', null=True),
        ),
    ]
