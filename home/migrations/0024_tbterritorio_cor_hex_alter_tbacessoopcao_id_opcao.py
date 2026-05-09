

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0023_tbacessoopcao_id_classe_tbacessoopcao_id_opcao_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbterritorio',
            name='cor_hex',
            field=models.CharField(db_column='CorHex', max_length=7, default='#ffffff', help_text='Cor em formato Hexadecimal (ex: #FFFFFF)'),
        migrations.AlterField(
            model_name='tbacessoopcao',
            name='id_opcao',
            field=models.ForeignKey(db_column='Id_Opcao', on_delete=django.db.models.deletion.DO_NOTHING, to='home.tbopcaojogo'),
        ),
    ]
