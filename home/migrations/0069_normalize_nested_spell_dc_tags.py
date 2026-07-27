import re

from django.db import migrations


SPELL_CD = re.compile(r"\bspell(?:-|_)save(?:-|_)cd:")


def normalize_nested_spell_dc_tags(apps, schema_editor):
    MagicItem = apps.get_model("home", "TbItemMagico")
    for item in MagicItem.objects.exclude(tags_json=[]):
        old_tags = list(item.tags_json or [])
        new_tags = [
            SPELL_CD.sub("spell.cd:", tag) if isinstance(tag, str) else tag
            for tag in old_tags
        ]
        if new_tags != old_tags:
            item.tags_json = new_tags
            item.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0068_generalize_magic_item_tags"),
    ]

    operations = [
        migrations.RunPython(
            normalize_nested_spell_dc_tags,
            migrations.RunPython.noop,
        ),
    ]
