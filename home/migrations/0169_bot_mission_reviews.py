import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0168_master_legacy_import'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='TbRevisaoMissaoBot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quest_id', models.CharField(max_length=100, unique=True)),
                ('guild_id', models.CharField(max_length=100)),
                ('master_discord_id', models.CharField(blank=True, db_index=True, default='', max_length=32)),
                ('master_name', models.CharField(blank=True, default='', max_length=150)),
                ('decision', models.CharField(max_length=16)),
                ('canonical_id', models.CharField(blank=True, default='', max_length=100)),
                ('adventures', models.PositiveIntegerField(blank=True, null=True)),
                ('master_mm', models.PositiveIntegerField(blank=True, null=True)),
                ('event_coins', models.PositiveIntegerField(default=0)),
                ('financial_mode', models.CharField(default='none', max_length=16)),
                ('evidence', models.JSONField(default=dict)),
                ('reviewed_at', models.DateTimeField(auto_now=True)),
                ('adventure_receipt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='home.tbaventuramestre')),
                ('credit_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='bot_mission_credits', to=settings.AUTH_USER_MODEL)),
                ('legacy_master', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='home.tbmestrelegado')),
                ('legacy_record', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='home.tbregistromestrelegado')),
                ('receipt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='home.tbtransacaomestre')),
                ('reviewed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bot_mission_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={'verbose_name': 'Revisao de missao do bot', 'verbose_name_plural': 'Revisoes de missoes do bot'},
        ),
    ]
