from django.db import migrations


OLD = "equiped{armadura_media}, no_stealth_disadvantage"
NEW = "equiped{armadura_media}, no_dadv:check{furtividade}"


def generalize_medium_armor_mastery(apps, schema_editor):
    Talent = apps.get_model("home", "TbTalento")
    for talent in Talent.objects.filter(slug="maestria-em-armaduras-medias"):
        old_tags = list(talent.tags_json or [])
        new_tags = [NEW if tag == OLD else tag for tag in old_tags]
        if new_tags != old_tags:
            talent.tags_json = new_tags
            talent.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0070_cleanup_magic_item_tag_syntax"),
    ]

    operations = [
        migrations.RunPython(
            generalize_medium_armor_mastery,
            migrations.RunPython.noop,
        ),
    ]
