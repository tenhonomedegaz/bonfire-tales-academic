from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0036_tbmaplayer_alter_tbrecursoclasse_tipo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tbbestiario',
            name='source',
        ),
    ]
