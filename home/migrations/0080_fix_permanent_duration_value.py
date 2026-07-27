from django.db import migrations


OLD = (
    "while_active{ requires{concentration}, "
    "on:concentration_end -> end, "
    "on:duration>=1min -> permanent }"
)
NEW = (
    "while_active{ requires{concentration}, "
    "on:concentration_end -> end, "
    "on:duration>=1min -> duration:permanent }"
)


def rewrite_duration(apps, schema_editor):
    Ability = apps.get_model("home", "TbClassehabilidade")
    for ability in Ability.objects.filter(nome="Troca Equivalente"):
        tags = [NEW if tag == OLD else tag for tag in list(ability.tags_json or [])]
        if tags != list(ability.tags_json or []):
            ability.tags_json = tags
            ability.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0079_refine_remaining_without_filters"),
    ]

    operations = [
        migrations.RunPython(rewrite_duration, migrations.RunPython.noop),
    ]
