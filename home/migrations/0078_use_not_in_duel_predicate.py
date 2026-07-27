from django.db import migrations


OLD = (
    "requires:{ equiped{weapon{melee}} and one_handed "
    "and without{other_weapon} }"
)
NEW = (
    "requires:{ equiped{weapon{melee}} and one_handed "
    "and not{other_weapon} }"
)


def rewrite_duel_requirement(apps, schema_editor):
    Option = apps.get_model("home", "TbOpcaojogo")
    for option in Option.objects.filter(nome="Duelo"):
        tags = [NEW if tag == OLD else tag for tag in list(option.tags_json or [])]
        if tags != list(option.tags_json or []):
            option.tags_json = tags
            option.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0077_model_redemption_as_scoped_mark"),
    ]

    operations = [
        migrations.RunPython(rewrite_duel_requirement, migrations.RunPython.noop),
    ]
