from django.db import migrations


def cleanup_magic_item_tag_syntax(apps, schema_editor):
    MagicItem = apps.get_model("home", "TbItemMagico")
    for item in MagicItem.objects.exclude(tags_json=[]):
        old_tags = list(item.tags_json or [])
        new_tags = []
        for tag in old_tags:
            if isinstance(tag, str):
                tag = tag.split("#", 1)[0].rstrip()
                tag = tag.replace(
                    "no_stealth_disadvantage",
                    "no_dadv:check{furtividade}",
                )
            if tag and tag not in new_tags:
                new_tags.append(tag)
        if new_tags != old_tags:
            item.tags_json = new_tags
            item.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0069_normalize_nested_spell_dc_tags"),
    ]

    operations = [
        migrations.RunPython(
            cleanup_magic_item_tag_syntax,
            migrations.RunPython.noop,
        ),
    ]
