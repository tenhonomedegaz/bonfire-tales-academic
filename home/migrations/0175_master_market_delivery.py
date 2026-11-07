import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0173_character_log_history')]

    operations = [
        migrations.AddField(
            model_name='tbrecompensamestre', name='efeito',
            field=models.CharField(max_length=24, default='manual', choices=[
                ('manual', 'Cumprimento manual'),
                ('aventura_recompensa', 'Uma aventura e ouro de progressao por unidade'),
            ], help_text='Contrato explicito; nome e descricao nunca determinam a entrega.')),
        migrations.AddField(
            model_name='tbtransacaomestre', name='operacao',
            field=models.CharField(max_length=32, unique=True, null=True, blank=True)),
        migrations.AddField(
            model_name='tbtransacaomestre', name='recompensa',
            field=models.ForeignKey(to='home.tbrecompensamestre',
                on_delete=django.db.models.deletion.PROTECT, null=True, blank=True)),
        migrations.AddField(
            model_name='tbtransacaomestre', name='personagem',
            field=models.ForeignKey(to='home.tbpersonagem',
                on_delete=django.db.models.deletion.PROTECT, null=True, blank=True,
                related_name='resgates_mestre')),
        migrations.AddField(
            model_name='tbtransacaomestre', name='quantidade',
            field=models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField(
            model_name='tbtransacaomestre', name='detalhes_json',
            field=models.JSONField(default=dict, blank=True)),
        migrations.AlterField(
            model_name='tbpersonagemaventura', name='origem',
            field=models.CharField(max_length=32, default='mesa', db_index=True, choices=[
                ('mesa', 'Mesa jogada'), ('recompensa_comunidade', 'Recompensa comunitária'),
                ('mercado_mestre', 'Resgate do Mercado de Mestre'),
            ])),
    ]
