from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0025_tbcronica_tbjornal'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbregiao',
            name='etiquetas_adicionais',
            field=models.TextField(blank=True, db_column='EtiquetasAdicionais', help_text='Tags adicionais separadas por vírgula.', null=True),
        ),
        migrations.AddField(
            model_name='tbregiao',
            name='mapa_url',
            field=models.CharField(blank=True, db_column='MapaUrl', help_text='URL ou caminho static do mapa lateral da região.', max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='tbcronica',
            name='regiao',
            field=models.TextField(blank=True, db_column='Regiao', help_text='Regiões específicas onde a crônica se passa.', null=True),
        ),
        migrations.AlterField(
            model_name='tbcronica',
            name='territorio',
            field=models.TextField(blank=True, db_column='Territorio', help_text='Territórios onde a crônica se passa.', null=True),
        ),
    ]
