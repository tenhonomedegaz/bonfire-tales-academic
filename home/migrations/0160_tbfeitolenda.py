from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('home', '0159_redesign_cosmetic_mm_prior_inventory')]

    operations = [
        migrations.CreateModel(
            name='TbFeitoLenda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=180)),
                ('descricao', models.TextField(max_length=4000)),
                ('data', models.DateField(blank=True, null=True)),
                ('ordem', models.PositiveIntegerField(default=0)),
                ('publicado', models.BooleanField(default=False, help_text='Publicar no memorial do personagem Lenda.')),
                ('personagem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name='feitos_lenda', to='home.tbpersonagem')),
            ],
            options={'ordering': ['ordem', 'data', 'pk'], 'verbose_name': 'Feito de Lenda',
                     'verbose_name_plural': 'Feitos de Lendas'},
        ),
    ]
