from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0004_tbtalento_alter_tbmapmarker_icone'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbtalento',
            name='etiquetas_adicionais',
            field=models.TextField(blank=True, db_column='EtiquetasAdicionais', help_text='Tags adicionais separadas por vírgula.', null=True),
        ),
        migrations.AddField(
            model_name='tbtalento',
            name='pre_requisito',
            field=models.TextField(blank=True, db_column='PreRequisito', help_text='Pré-requisitos do talento.', null=True),
        ),
    ]
