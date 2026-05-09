

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0013_alter_tbacessoopcao_options_alter_tbclasse_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tbmapmarker',
            name='icone',
        ),
    ]
