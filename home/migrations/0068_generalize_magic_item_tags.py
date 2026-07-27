import re

from django.db import migrations


METADATA_PREFIXES = ("item:", "raridade:", "slot:", "loja:", "tipo:")
SPELL_CD = re.compile(r"^spell(?:-|_)save(?:-|_)cd:(.*)$")
ATTR_FLOOR = re.compile(r"^attr_set:([a-z]{3})_score=(\d+)$")


def generalize_magic_item_tags(apps, schema_editor):
    MagicItem = apps.get_model("home", "TbItemMagico")
    for item in MagicItem.objects.exclude(tags_json=[]):
        old_tags = list(item.tags_json or [])
        new_tags = []
        for tag in old_tags:
            if not isinstance(tag, str):
                new_tags.append(tag)
                continue
            if tag.startswith(METADATA_PREFIXES):
                continue
            spell_cd = SPELL_CD.match(tag)
            if spell_cd:
                tag = "spell.cd:%s" % spell_cd.group(1)
            attr_floor = ATTR_FLOOR.match(tag)
            if attr_floor:
                attr, score = attr_floor.groups()
                tag = "attr:%s_score:=max(%s_score,%s)" % (
                    attr, attr, score)
            if tag not in new_tags:
                new_tags.append(tag)
        if new_tags != old_tags:
            item.tags_json = new_tags
            item.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0067_generalize_keen_mind_context"),
    ]

    operations = [
        migrations.RunPython(
            generalize_magic_item_tags,
            migrations.RunPython.noop,
        ),
    ]
