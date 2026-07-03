# -*- coding: utf-8 -*-
"""F2 — campos de vitrine de personalização no UserProfile.

- titulo_equipado: slug de um cosmético tipo=titulo exibido sob o nome.
- badges_destaque: lista de slugs de badges que o usuário fixa na vitrine (até 6).

Dado de USUÁRIO (não entra no sync de conteúdo). Sem default destrutivo.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0048_seed_cosmeticos'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='titulo_equipado',
            field=models.CharField(blank=True, db_column='TituloEquipado', default='',
                                   help_text='Slug de um cosmético tipo=titulo equipado sob o nome.',
                                   max_length=60),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='badges_destaque',
            field=models.JSONField(blank=True, db_column='BadgesDestaque', default=list,
                                   help_text='Slugs de badges concedidas que o usuário fixa na vitrine (até 6).'),
        ),
    ]
