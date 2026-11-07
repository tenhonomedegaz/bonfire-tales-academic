from django.db import migrations


REPLACEMENTS = (
    (
        "requires:{ equiped{weapon{melee}} and one_handed "
        "and without{other_weapon} }",
        "requires:{ equiped{weapon{melee}} and one_handed "
        "and not{other_weapon} }",
    ),
    (
        "instant{ without{limit:1_tecnica_por_ataque} }",
        "instant{ suppress{limit:1_tecnica_por_ataque} }",
    ),
    (
        "resource_cost:dados_sombrios:1(if without{free_use})",
        "resource_cost:dados_sombrios:1(if not{free_use})",
    ),
    (
        "dmg:1d10(forca)/1.5ft_deslocado(without{reduction})",
        "dmg:1d10(forca)/1.5ft_deslocado(ignore:dmg_reduction)",
    ),
    (
        "redirect_damage:overflow(target:self, without{reduction})",
        "redirect_damage:overflow(target:self, ignore:dmg_reduction)",
    ),
    (
        "while_active{ without{concentration_break} }",
        "while_active{ suppress{concentration_break} }",
    ),
    (
        "without{reveal_on:miss{ requires:hidden }}",
        "suppress{reveal_on:miss{ requires:hidden }}",
    ),
    (
        "without{flanking_against_self{ requires:weapon{arma_dupla} }}",
        "suppress{flanking:against_self, requires:weapon{arma_dupla}}",
    ),
    (
        "spell_selection.lista{nivel:1, without{dmg}, "
        "without{concentration}, always_prepared",
        "spell_selection.lista{nivel:1, not{dmg}, "
        "not{concentration}, always_prepared",
    ),
    (
        "without{concentration}, qtd:1, spell_mod:",
        "not{concentration}, qtd:1, spell_mod:",
    ),
    (
        "pick:raca_humanoide:1(requires:raca!=self, without{essencia})",
        "pick:raca_humanoide:1(requires:raca!=self, exclude:essencia)",
    ),
    (
        "trigger=cast{dmg, without{weapon_attack}}",
        "trigger=cast{dmg, not{weapon_attack}}",
    ),
    (
        "size:={ without{slot:miudo}, classlvl=1:pequeno }",
        "size:=match(spell_slot_level){"
        "0:miudo, 1:pequeno, 3:medio, 5:grande, "
        "7:enorme, 9:descomunal}",
    ),
    (
        "while_active{ restriction:without{concentration} }",
        "while_active{ requires{concentration}, "
        "on:concentration_end -> end, "
        "on:duration>=1min -> permanent }",
    ),
)


def rewrite_remaining_filters(apps, schema_editor):
    model_names = (
        "TbClassehabilidade",
        "TbTalento",
        "TbOpcaojogo",
        "TbTracoracial",
        "TbItemMagico",
    )
    for model_name in model_names:
        Model = apps.get_model("home", model_name)
        for obj in Model.objects.exclude(tags_json__isnull=True).iterator():
            old_tags = list(obj.tags_json or [])
            new_tags = []
            for tag in old_tags:
                text = str(tag)
                for old, new in REPLACEMENTS:
                    text = text.replace(old, new)
                new_tags.append(text)
            if new_tags != old_tags:
                obj.tags_json = new_tags
                obj.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0078_use_not_in_duel_predicate"),
    ]

    operations = [
        migrations.RunPython(
            rewrite_remaining_filters,
            migrations.RunPython.noop,
        ),
    ]
