import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0183_management_character_profile_permission'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name='CharacterStorySubmission',
        fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('request_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ('text', models.TextField(max_length=5000)),
            ('text_digest', models.CharField(max_length=64)),
            ('status', models.CharField(choices=[('pending', 'Aguardando aprovação'), ('approved', 'Aprovada'),
                ('changes', 'Ajustes solicitados'), ('superseded', 'Substituída por novo envio')],
                db_index=True, default='pending', max_length=16)),
            ('feedback', models.TextField(blank=True, max_length=3000)),
            ('submitted_at', models.DateTimeField(auto_now_add=True)),
            ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ('author', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='character_stories', to=settings.AUTH_USER_MODEL)),
            ('character', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='story_submissions', to='home.tbpersonagem')),
            ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='reviewed_character_stories', to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-submitted_at', '-pk'], 'default_permissions': (),
            'constraints': [models.UniqueConstraint(condition=models.Q(status='pending'),
                fields=('character',), name='one_pending_character_story')]},
    )]
