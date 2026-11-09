from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0177_history_master_reservation')]

    operations = [migrations.AddField(
        model_name='tbopcaojogo', name='arquivado',
        field=models.BooleanField(default=False, help_text='Oculta de novos catalogos e escolhas, preservando fichas e revisoes existentes.'))]
