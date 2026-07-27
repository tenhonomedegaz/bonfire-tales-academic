from django.db import migrations


OLD_TAGS = {
    "duration:100": "duration:10",
    "while_active{ move:darkvision(range:120ft, magical) }": (
        "while_active{ sense:darkvision(range:120ft), "
        "sense:devilsight(range:120ft) }"
    ),
}


def normalize_astral_visage(apps, schema_editor):
    Ability = apps.get_model("home", "TbClassehabilidade")
    for ability in Ability.objects.filter(nome="Aspecto da Alma Astral"):
        old_tags = list(ability.tags_json or [])
        new_tags = [OLD_TAGS.get(tag, tag) for tag in old_tags]
        if new_tags != old_tags:
            ability.tags_json = new_tags
            ability.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0074_cleanup_phantasmal_strike_effect_reference"),
    ]

    operations = [
        migrations.RunPython(
            normalize_astral_visage,
            migrations.RunPython.noop,
        ),
    ]
