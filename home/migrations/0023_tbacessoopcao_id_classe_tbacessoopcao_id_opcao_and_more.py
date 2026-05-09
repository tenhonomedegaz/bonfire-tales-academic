

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0022_alter_tbacessoopcao_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbacessoopcao',
            name='id_classe',
            field=models.ForeignKey(blank=True, db_column='Id_Classe', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='home.tbclasse'),
        ),
        migrations.AddField(
            model_name='tbacessoopcao',
            name='id_opcao',
            field=models.ForeignKey(blank=True, db_column='Id_Opcao', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='home.tbopcaojogo'),
        ),
        migrations.AddField(
            model_name='tbacessoopcao',
            name='id_subclasse',
            field=models.ForeignKey(blank=True, db_column='Id_Subclasse', null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='home.tbsubclasse'),
        ),
        migrations.AddField(
            model_name='tbopcaojogo',
            name='etiquetas_adicionais',
            field=models.CharField(blank=True, db_column='EtiquetasAdicionais', max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='tbopcaojogo',
            name='pre_requisito',
            field=models.TextField(blank=True, db_column='PreRequisito', null=True),
        ),
    ]
