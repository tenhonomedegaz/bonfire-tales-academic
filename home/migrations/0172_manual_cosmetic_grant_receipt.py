import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('home', '0171_unique_account_email'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='ManualCosmeticGrantReceipt',
        fields=[
            ('request_id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('motivo', models.CharField(max_length=500)),
            ('payload_digest', models.CharField(editable=False, max_length=64)),
            ('outcome', models.CharField(choices=[('granted', 'Concedido'), ('already_owned', 'Ja possuido')], max_length=20)),
            ('criado_em', models.DateTimeField(auto_now_add=True)),
            ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='management_cosmetic_actions', to=settings.AUTH_USER_MODEL)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='management_cosmetic_receipts', to=settings.AUTH_USER_MODEL)),
            ('cosmetico', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='management_grant_receipts', to='home.tbcosmetico')),
            ('inventory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='management_receipts', to='home.tbusuariocosmetico')),
        ],
        options={'ordering': ['-criado_em', '-request_id'], 'default_permissions': (), 'permissions': [
            ('view_management_people', 'Consultar pessoas na Central de Gestao'),
            ('view_management_cosmetics', 'Consultar inventarios na Central de Gestao'),
            ('grant_management_cosmetic', 'Conceder cosmetico manual pela Central de Gestao')]},
    )]
