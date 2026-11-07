from django.db import migrations


OLD = (
    "always_active{ resist:source{creature}, trigger=hit_by_attack, "
    "instant{ dmg:half(damage_taken)(radiante) }, "
    "restriction{attack_target | cast_target | dmg_target} }"
)

NEW = (
    "always_active{ restriction{mark{redemption_broken, target:source}}, "
    "resist:source{creature}, trigger=hit_by_attack, "
    "instant{dmg:half(damage_taken)(radiante)} }"
)

TRIGGER = (
    "trigger={attack(target:creature) | cast(target:creature) | "
    "dmg(target:creature, except:ability{emissario_da_redencao, "
    "classe:paladino})} -> instant{mark{redemption_broken, target:target, "
    "duration:until_long_rest}}"
)


def rewrite_redemption(apps, schema_editor):
    Ability = apps.get_model("home", "TbClassehabilidade")
    for ability in Ability.objects.filter(nome="Emissário da Redenção"):
        tags = [NEW if tag == OLD else tag for tag in list(ability.tags_json or [])]
        if TRIGGER not in tags:
            tags.append(TRIGGER)
        if tags != list(ability.tags_json or []):
            ability.tags_json = tags
            ability.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0076_refine_negation_and_sense_semantics"),
    ]

    operations = [
        migrations.RunPython(rewrite_redemption, migrations.RunPython.noop),
    ]
