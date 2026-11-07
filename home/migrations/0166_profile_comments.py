import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models.functions import Length
from django.db.models.lookups import LessThanOrEqual


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0165_rank_themes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TbPerfilComentario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('texto', models.TextField(db_column='Texto', max_length=4000)),
                ('chave_operacao', models.UUIDField(db_column='ChaveOperacao', unique=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_column='CriadoEm')),
                ('removido_em', models.DateTimeField(blank=True, db_column='RemovidoEm', null=True)),
                ('autor', models.ForeignKey(db_column='AutorId', on_delete=django.db.models.deletion.CASCADE,
                                           related_name='perfil_comentarios_escritos', to=settings.AUTH_USER_MODEL)),
                ('perfil', models.ForeignKey(db_column='PerfilId', on_delete=django.db.models.deletion.CASCADE,
                                            related_name='perfil_comentarios_recebidos', to=settings.AUTH_USER_MODEL)),
                ('removido_por', models.ForeignKey(blank=True, db_column='RemovidoPorId', null=True,
                                                  on_delete=django.db.models.deletion.SET_NULL,
                                                  related_name='perfil_comentarios_removidos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'TB_PerfilComentario', 'ordering': ['-criado_em', '-pk'],
                'indexes': [
                    models.Index(fields=['perfil', 'removido_em', '-criado_em', '-id'], name='perfil_wall_recent_idx'),
                    models.Index(fields=['autor', 'criado_em'], name='perfil_wall_rate_idx'),
                ],
                'constraints': [
                    models.CheckConstraint(condition=(~models.Q(texto='') & LessThanOrEqual(Length('texto'), 4000)),
                                           name='perfil_comment_text_length'),
                    models.CheckConstraint(condition=(models.Q(removido_em__isnull=False) |
                                                       models.Q(removido_por__isnull=True)),
                                           name='perfil_comment_removal_state'),
                ],
            },
        ),
        migrations.CreateModel(
            name='TbPerfilComentarioCurtida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_column='CriadoEm')),
                ('comentario', models.ForeignKey(db_column='ComentarioId', on_delete=django.db.models.deletion.CASCADE,
                                                related_name='curtidas', to='home.tbperfilcomentario')),
                ('quem', models.ForeignKey(db_column='QuemId', on_delete=django.db.models.deletion.CASCADE,
                                          related_name='perfil_comentario_curtidas', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'TB_PerfilComentarioCurtida',
                'constraints': [models.UniqueConstraint(fields=('comentario', 'quem'), name='perfil_comment_like_unique')],
            },
        ),
    ]
