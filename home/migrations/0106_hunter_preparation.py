from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('home', '0105_immutable_content_guards')]
    operations = [
        migrations.CreateModel(
            name='TbPersonagemCacador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ability', models.CharField(choices=[('int', 'Inteligência'), ('wis', 'Sabedoria')], max_length=3)),
                ('selected', models.JSONField(default=list)),
                ('version', models.PositiveIntegerField(default=0)),
                ('personagem_classe', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                    related_name='cacador_rework', to='home.tbpersonagemclasse')),
                ('ruleset', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='home.tbruleset')),
            ],
            options={'constraints': [models.CheckConstraint(
                condition=models.Q(ability__in=['int', 'wis']), name='hunter_valid_ability')]},
        ),
    ]
