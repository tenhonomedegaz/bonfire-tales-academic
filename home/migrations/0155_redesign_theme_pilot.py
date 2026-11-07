from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0154_redesign_master_portfolio')]

    operations = [
        migrations.AddField(
            model_name='cosmeticcheckoutoffer', name='demonstration',
            field=models.BooleanField(
                default=False, help_text='Preço ilustrativo; nunca inicia cobrança ou débito MM.'),
        ),
    ]
