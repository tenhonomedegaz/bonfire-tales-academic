import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0121_tbusuarioconquista_revogada_em_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ManagedApiKey',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('prefix', models.CharField(db_index=True, max_length=16, unique=True)),
                ('secret_hash', models.CharField(editable=False, max_length=64)),
                ('scopes', models.JSONField(default=list)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('rate_window_started', models.DateTimeField(blank=True, null=True)),
                ('rate_count', models.PositiveIntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_api_keys_created', to=settings.AUTH_USER_MODEL)),
                ('rotated_from', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rotations', to='home.managedapikey')),
            ],
            options={
                'verbose_name': 'Chave de API gerenciada',
                'verbose_name_plural': 'Chaves de API gerenciadas',
                'db_table': 'home_managed_api_key',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='DbAccessAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=24)),
                ('model_label', models.CharField(blank=True, max_length=64)),
                ('object_pk', models.CharField(blank=True, max_length=100)),
                ('status_code', models.PositiveSmallIntegerField()),
                ('field_names', models.JSONField(blank=True, default=list)),
                ('occurred_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('api_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='home.managedapikey')),
            ],
            options={
                'verbose_name': 'Auditoria de acesso ao banco',
                'verbose_name_plural': 'Auditorias de acesso ao banco',
                'db_table': 'home_db_access_audit',
                'ordering': ('-occurred_at',),
            },
        ),
        migrations.CreateModel(
            name='DbAccessIdempotency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key_hash', models.CharField(max_length=64)),
                ('request_hash', models.CharField(max_length=64)),
                ('status_code', models.PositiveSmallIntegerField()),
                ('response_json', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('api_key', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='home.managedapikey')),
            ],
            options={'db_table': 'home_db_access_idempotency'},
        ),
        migrations.AddConstraint(
            model_name='dbaccessidempotency',
            constraint=models.UniqueConstraint(fields=('api_key', 'key_hash'), name='home_db_access_idempotency_key_unique'),
        ),
    ]
