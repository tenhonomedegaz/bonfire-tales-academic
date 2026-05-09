

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0021_tbterritorio_coordenadas_poligono'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tbacessoopcao',
            options={'managed': True, 'verbose_name': 'Acesso de Opção', 'verbose_name_plural': 'Acessos de Opções'},
        ),
        migrations.AlterModelOptions(
            name='tbopcaojogo',
            options={'managed': True, 'verbose_name': 'Opção de Jogo', 'verbose_name_plural': 'Opções de Jogo'},
        ),
        migrations.AddField(
            model_name='tbacessoopcao',
            name='nivel_recebimento',
            field=models.IntegerField(db_column='NivelRecebimento', default=1),
        ),
        migrations.AddField(
            model_name='tbopcaojogo',
            name='pre_requisito',
            field=models.TextField(blank=True, db_column='PreRequisito', null=True, help_text='Pré-requisitos da opção.'),
        ),
    ]
