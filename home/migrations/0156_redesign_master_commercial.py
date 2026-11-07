import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    # This B branch can be applied without the independent D pilot field in 0155.
    dependencies = [('home', '0154_redesign_master_portfolio'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name='TbVerificacaoMesa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('aberta', models.BooleanField(default=False)),
                ('validada', models.BooleanField(default=False)),
                ('observacao', models.CharField(blank=True, default='', max_length=800)),
                ('validado_em', models.DateTimeField(auto_now=True)),
                ('aventura', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name='verificacao_vitrine', to='home.tbaventuramestre')),
                ('validado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='mesas_verificadas', to=settings.AUTH_USER_MODEL)),
            ], options={'verbose_name':'Mesa realizada e verificada',
                        'verbose_name_plural':'Mesas realizadas e verificadas'},
        ),
        migrations.CreateModel(
            name='TbAutorizacaoVitrine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('autorizada', models.BooleanField(default=False)),
                ('observacao', models.CharField(blank=True, default='', max_length=800)),
                ('avaliado_em', models.DateTimeField(auto_now=True)),
                ('avaliado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                    related_name='autorizacoes_vitrine', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                    related_name='autorizacao_vitrine', to=settings.AUTH_USER_MODEL)),
            ], options={'verbose_name':'Autorização comercial da vitrine',
                        'verbose_name_plural':'Autorizações comerciais da vitrine'},
        ),
    ]
