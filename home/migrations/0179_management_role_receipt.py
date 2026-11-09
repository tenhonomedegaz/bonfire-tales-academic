import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('home', '0178_option_archive'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='ManagementRoleReceipt',
        fields=[
            ('request_id', models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False, serialize=False)),
            ('before_roles', models.JSONField(default=list)),
            ('after_roles', models.JSONField(default=list)),
            ('motivo', models.CharField(max_length=500)),
            ('payload_digest', models.CharField(max_length=64)),
            ('criado_em', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='management_role_actions', to=settings.AUTH_USER_MODEL)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='management_role_receipts', to=settings.AUTH_USER_MODEL)),
        ], options={'default_permissions': (), 'ordering': ['-criado_em']})]
