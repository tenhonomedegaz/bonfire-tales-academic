import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0114_cronica_revisao_edicao'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TbCronicaCurtida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_column='CriadoEm')),
                ('cronica', models.ForeignKey(db_column='CronicaId', on_delete=django.db.models.deletion.CASCADE, related_name='curtidas', to='home.tbcronica')),
                ('leitor', models.ForeignKey(db_column='LeitorId', on_delete=django.db.models.deletion.CASCADE, related_name='cronicas_curtidas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'TB_CronicaCurtida',
                'constraints': [models.UniqueConstraint(fields=('cronica', 'leitor'), name='unique_cronica_curtida_leitor')],
            },
        ),
    ]
