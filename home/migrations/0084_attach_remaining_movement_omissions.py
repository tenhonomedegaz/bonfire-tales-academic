from django.db import migrations


REPLACEMENTS = {
    "if(dmg_reduced_to:0): move:10ft, without{opportunity_attack}": (
        "if(dmg_reduced_to:0): "
        "move:10ft(without{opportunity_attack})"
    ),
    "instant{ move:full, without{opportunity_attack} }": (
        "instant{ move:full(without{opportunity_attack}) }"
    ),
}


def attach_movement_omissions(apps, schema_editor):
    Trait = apps.get_model("home", "TbTracoracial")
    for trait in Trait.objects.exclude(tags_json__isnull=True).iterator():
        old_tags = list(trait.tags_json or [])
        new_tags = []
        for tag in old_tags:
            text = str(tag)
            for old, new in REPLACEMENTS.items():
                text = text.replace(old, new)
            new_tags.append(text)
        if new_tags != old_tags:
            trait.tags_json = new_tags
            trait.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0083_attach_without_to_owning_operations"),
    ]

    operations = [
        migrations.RunPython(
            attach_movement_omissions,
            migrations.RunPython.noop,
        ),
    ]
