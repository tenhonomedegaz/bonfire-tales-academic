from django.db import migrations


OLD = (
    "instant{ on:reflexo_espiritual -> "
    "apply:golpe_fantasmagorico(targets:both, cost:=0) }"
)
NEW = (
    "instant{ on:reflexo_espiritual -> "
    "activate:ability{golpe_fantasmagorico, classe:ladino}"
    "(targets:both, cost:=0) }"
)


def rewrite_reference(apps, schema_editor):
    Ability = apps.get_model("home", "TbClassehabilidade")
    for ability in Ability.objects.filter(nome="Coro dos Mortos"):
        old_tags = list(ability.tags_json or [])
        new_tags = [NEW if tag == OLD else tag for tag in old_tags]
        if new_tags != old_tags:
            ability.tags_json = new_tags
            ability.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0073_generalize_conditions_negation_and_dice"),
    ]

    operations = [
        migrations.RunPython(
            rewrite_reference,
            migrations.RunPython.noop,
        ),
    ]
