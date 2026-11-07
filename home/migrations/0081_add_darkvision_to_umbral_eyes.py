from django.db import migrations


def add_base_darkvision(apps, schema_editor):
    Trait = apps.get_model("home", "TbTracoracial")
    for trait in Trait.objects.filter(nome="Olhos do Véu Umbral"):
        tags = list(trait.tags_json or [])
        devil_index = next(
            (
                index for index, tag in enumerate(tags)
                if tag.startswith("sense:devilsight")
            ),
            len(tags),
        )
        if not any(tag.startswith("sense:darkvision") for tag in tags):
            tags.insert(devil_index, "sense:darkvision")
        if tags != list(trait.tags_json or []):
            trait.tags_json = tags
            trait.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0080_fix_permanent_duration_value"),
    ]

    operations = [
        migrations.RunPython(add_base_darkvision, migrations.RunPython.noop),
    ]
