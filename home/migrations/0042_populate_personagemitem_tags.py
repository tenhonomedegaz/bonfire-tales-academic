# -*- coding: utf-8 -*-
"""Popula TbPersonagemItem.tags_json a partir do snapshot de CA antigo (tipo_equip/
ca_base/ca_limite_des) ANTES de essas colunas serem removidas. Torna as tags a fonte
unica da mecanica do item equipado (CA calc passa a ler daqui)."""
from django.db import migrations


def populate(apps, schema_editor):
    PI = apps.get_model('home', 'TbPersonagemItem')
    for it in PI.objects.all():
        if it.tags_json:
            continue
        te = (it.tipo_equip or '').strip().lower()
        tags = []
        if te == 'escudo' and it.ca_base is not None:
            tags.append('ca:+%d' % it.ca_base)
        elif te.startswith('armadura') and it.ca_base is not None:
            tags.append('ca=%d' % it.ca_base)
            if it.ca_limite_des is not None:
                tags.append('dex-ca-max:%d' % it.ca_limite_des)
        if tags:
            it.tags_json = tags
            it.save(update_fields=['tags_json'])


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('home', '0041_tbpersonagemitem_tags_json')]
    operations = [migrations.RunPython(populate, reverse)]
