from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0037_remove_tbbestiario_source'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tbarmadilha',
            name='source',
        ),
    ]
