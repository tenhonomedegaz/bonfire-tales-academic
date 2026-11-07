import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import home.vtt_lab_models


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0166_profile_comments'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VttLabSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nome', models.CharField(max_length=120)),
                ('state', models.JSONField(default=home.vtt_lab_models.initial_lab_state)),
                ('revision', models.PositiveBigIntegerField(default=0)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='vtt_lab_sessions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'db_table': 'TB_VttLabSession', 'ordering': ['-atualizado_em', '-id'],
                     'indexes': [models.Index(fields=['owner', '-atualizado_em'], name='vtt_lab_owner_updated_idx')]},
        ),
        migrations.CreateModel(
            name='VttLabReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('command_id', models.UUIDField()),
                ('payload_hash', models.CharField(max_length=64)),
                ('revision', models.PositiveBigIntegerField()),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name='receipts', to='home.vttlabsession')),
            ],
            options={'db_table': 'TB_VttLabReceipt', 'constraints': [models.UniqueConstraint(
                fields=('session', 'command_id'), name='vtt_lab_command_unique')]},
        ),
    ]
