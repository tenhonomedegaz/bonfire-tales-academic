import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0100_personagem_magia_assinatura'),
    ]

    operations = [
        migrations.CreateModel(
            name='TbPersonagemEstado',
            fields=[
                ('id', models.AutoField(db_column='Id', primary_key=True, serialize=False)),
                ('chave', models.CharField(db_column='Chave', max_length=180)),
                ('origem', models.CharField(blank=True, db_column='Origem', default='', max_length=180)),
                ('payload_json', models.JSONField(blank=True, db_column='PayloadJSON', default=dict)),
                ('ends_on_json', models.JSONField(blank=True, db_column='EndsOnJSON', default=list)),
                ('ativo', models.BooleanField(db_column='Ativo', db_index=True, default=True)),
                ('iniciado_em', models.DateTimeField(auto_now_add=True, db_column='IniciadoEm')),
                ('encerrado_em', models.DateTimeField(blank=True, db_column='EncerradoEm', null=True)),
            ],
            options={
                'db_table': 'TB_PersonagemEstado',
            },
        ),
        migrations.AddField(
            model_name='tbanuncioitemmagico',
            name='estado_json',
            field=models.JSONField(blank=True, db_column='EstadoJSON', default=dict, help_text='Snapshot de estado persistente da instancia, como cargas restantes.'),
        ),
        migrations.AddField(
            model_name='tbpersonagemrecurso',
            name='chave',
            field=models.CharField(blank=True, db_column='Chave', db_index=True, default='', help_text='Identidade mecanica estavel; o nome e apenas apresentacao.', max_length=180),
        ),
        migrations.AddField(
            model_name='tbpersonagemrecurso',
            name='id_item',
            field=models.ForeignKey(blank=True, db_column='Id_Item', help_text='Instancia dona do recurso quando ele representa cargas de item.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='recursos', to='home.tbpersonagemitem'),
        ),
        migrations.AddField(
            model_name='tbpersonagemrecurso',
            name='origem',
            field=models.CharField(blank=True, db_column='Origem', default='', help_text='Fonte declarativa do recurso: classe, habilidade, magia ou item.', max_length=180),
        ),
        migrations.AddField(
            model_name='tbpersonagemrecurso',
            name='recuperacao',
            field=models.CharField(blank=True, db_column='Recuperacao', default='', help_text='Formula recuperada no evento; vazio significa recuperar ate o maximo.', max_length=80),
        ),
        migrations.AddField(
            model_name='tbpersonagemrecurso',
            name='reset',
            field=models.CharField(blank=True, db_column='Reset', default='', help_text='Evento de recuperacao declarado pela tag.', max_length=40),
        ),
        migrations.AddConstraint(
            model_name='tbpersonagemrecurso',
            constraint=models.UniqueConstraint(condition=models.Q(('chave', ''), _negated=True), fields=('id_personagem', 'chave'), name='uniq_recurso_personagem_chave'),
        ),
        migrations.AddField(
            model_name='tbpersonagemestado',
            name='id_personagem',
            field=models.ForeignKey(db_column='Id_Personagem', on_delete=django.db.models.deletion.CASCADE, related_name='estados', to='home.tbpersonagem'),
        ),
        migrations.AddConstraint(
            model_name='tbpersonagemestado',
            constraint=models.UniqueConstraint(fields=('id_personagem', 'chave'), name='uniq_estado_personagem_chave'),
        ),
    ]
