import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from home.email_cleanup_v1 import cleanup_and_index


class Migration(migrations.Migration):
    dependencies = [('home', '0170_master_application_answers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.AlterField(model_name='userprofile', name='email_verified', field=models.BooleanField(
            db_column='EmailVerified', default=False,
            help_text='E-mail confirmado por link de verificação. Todo endereço não vazio é exclusivo de uma conta.')),
        migrations.CreateModel(name='UserAccountMergeReceipt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('removed_user_id', models.PositiveIntegerField(unique=True)),
            ('removed_username', models.CharField(max_length=150)),
            ('email_verification_preserved', models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('keeper', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='account_merge_receipts', to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.RunPython(cleanup_and_index),
    ]
