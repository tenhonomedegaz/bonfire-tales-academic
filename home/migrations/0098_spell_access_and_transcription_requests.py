# Generated manually for the spell access/workshop contracts.
import re
import unicodedata

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _key(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = value.encode('ascii', 'ignore').decode('ascii').lower().strip()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def populate_spell_class_slugs(apps, schema_editor):
    Classe = apps.get_model('home', 'TbClasse')
    Magia = apps.get_model('home', 'TbMagia')
    lookup = {}
    for classe in Classe.objects.all():
        lookup[_key(classe.slug)] = classe.slug
        lookup[_key(classe.nome)] = classe.slug
    for magia in Magia.objects.all().iterator():
        slugs = []
        for token in re.split(r'[,;|]', magia.classes or ''):
            slug = lookup.get(_key(token))
            if slug and slug not in slugs:
                slugs.append(slug)
        magia.classes_slugs = slugs
        magia.save(update_fields=['classes_slugs'])


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0097_character_build_revisions'),
    ]

    operations = [
        migrations.AddField(
            model_name='tbmagia',
            name='classes_slugs',
            field=models.JSONField(
                blank=True,
                db_column='ClassesSlugs',
                default=list,
                help_text=(
                    'Fonte mecanica do acesso base: slugs validos de TbClasse. '
                    'O campo Classes permanece apenas como rotulo legivel e compatibilidade.'
                ),
            ),
        ),
        migrations.AlterField(
            model_name='tbpersonagemitem',
            name='origem_tipo',
            field=models.CharField(
                choices=[
                    ('legado', 'Legado'), ('criacao', 'Criacao de ficha'),
                    ('compra', 'Compra oficial'),
                    ('comunidade', 'Mercado da comunidade'),
                    ('oficina', 'Oficina de Magia'),
                    ('concessao', 'Concessao da staff'),
                    ('pathbuilder', 'Pathbuilder'),
                ],
                db_column='OrigemTipo', default='legado',
                help_text='Origem auditavel da linha para rebuild e reembolso seguro.',
                max_length=20, db_index=True,
            ),
        ),
        migrations.RunPython(populate_spell_class_slugs, migrations.RunPython.noop),
        migrations.CreateModel(
            name='TbSolicitacaoTranscricao',
            fields=[
                ('id_solicitacao', models.AutoField(db_column='Id_Solicitacao', primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('pendente', 'Pendente'), ('aceita', 'Aceita'), ('recusada', 'Recusada'), ('cancelada', 'Cancelada'), ('invalida', 'Invalidada')], db_column='Status', db_index=True, default='pendente', max_length=12)),
                ('custo_po', models.DecimalField(db_column='CustoPO', decimal_places=2, default=0, max_digits=10)),
                ('tempo_horas', models.DecimalField(db_column='TempoHoras', decimal_places=2, default=0, max_digits=8)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_column='CriadoEm')),
                ('respondido_em', models.DateTimeField(blank=True, db_column='RespondidoEm', null=True)),
                ('detalhes_json', models.JSONField(blank=True, db_column='DetalhesJSON', default=dict)),
                ('classe_solicitante', models.ForeignKey(db_column='Id_ClasseSolicitante', on_delete=django.db.models.deletion.PROTECT, related_name='solicitacoes_transcricao', to='home.tbclasse')),
                ('fonte', models.ForeignKey(db_column='Id_Fonte', on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_transcricao_recebidas', to='home.tbpersonagem')),
                ('magia', models.ForeignKey(db_column='Id_Magia', on_delete=django.db.models.deletion.PROTECT, related_name='solicitacoes_transcricao', to='home.tbmagia')),
                ('respondido_por', models.ForeignKey(blank=True, db_column='RespondidoPor', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='solicitacoes_transcricao_respondidas', to=settings.AUTH_USER_MODEL)),
                ('solicitante', models.ForeignKey(db_column='Id_Solicitante', on_delete=django.db.models.deletion.CASCADE, related_name='solicitacoes_transcricao_enviadas', to='home.tbpersonagem')),
            ],
            options={
                'verbose_name': 'Solicitacao de transcricao',
                'verbose_name_plural': 'Solicitacoes de transcricao',
                'db_table': 'TB_SolicitacaoTranscricao',
                'ordering': ['-criado_em', '-id_solicitacao'],
            },
        ),
        migrations.AddConstraint(
            model_name='tbsolicitacaotranscricao',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'pendente')),
                fields=('solicitante', 'fonte', 'magia', 'classe_solicitante'),
                name='uniq_transcricao_pendente',
            ),
        ),
    ]
