from django.db import migrations


REPLACEMENTS = (
    (
        "without{somatic(requires:equiped{weapon | shield})}",
        "suppress{restriction{somatic, requires:equiped{weapon | shield}}}",
    ),
    (
        "on:roll_max_or_min(hit_die) -> "
        "resource_restore:dados_de_vida:1, without{use_consumed}",
        "on:roll_max_or_min(hit_die) -> "
        "resource_restore:dados_de_vida:1(without{use_consumed})",
    ),
    (
        "trigger=leave_melee{voluntary, first/turn}",
        "trigger=leave_melee{voluntary, first/turn}"
        "(without{opportunity_attack})",
    ),
    (
        "instant{ move:toward_attacker(=roundup(speed/2)), "
        "without{opportunity_attack} }",
        "instant{ move:toward_attacker("
        "=roundup(speed/2), without{opportunity_attack}) }",
    ),
    (
        "dmg:+wis_mod(pick:{raio | fogo | frio | trovejante}), "
        "without{crit_mult}",
        "dmg:+wis_mod(pick:{raio | fogo | frio | trovejante})"
        "(without{crit_mult})",
    ),
    (
        "instant{ move:(speed/2), without{opportunity_attack} }",
        "instant{ move:(speed/2)(without{opportunity_attack}) }",
    ),
    (
        "instant{ move:5ft, without{opportunity_attack} }",
        "instant{ move:5ft(without{opportunity_attack}) }",
    ),
    (
        "instant{ speed:+30ft, "
        "grant:ability{movimento_fantasma, classe:mistico}(without{cost}), "
        "without{opportunity_attacks} }",
        "instant{ speed:+30ft, "
        "grant:ability{movimento_fantasma, classe:mistico}"
        "(without{cost}, without{opportunity_attacks}) }",
    ),
    (
        "instant{ push:5ft(target:all, from:aura), "
        "without{opportunity_attack} }",
        "instant{ push:5ft(target:all, from:aura, "
        "without{opportunity_attack}) }",
    ),
    (
        "instant{ move:half_speed, without{opportunity_attack} }",
        "instant{ move:half_speed(without{opportunity_attack}) }",
    ),
    (
        "instant{ without{attack_roll}, aoe{ line:30ft, save{dex, "
        "cd=8+pb+wis_mod}, on_fail{ "
        "dmg:weapon_die+2d(resource{dado_de_combate})(perfurante) }, "
        "on_success{ dmg:half } } }",
        "instant{ attack:replace{without{attack_roll}, aoe{line:30ft, "
        "save{dex, cd=8+pb+wis_mod}, "
        "on_fail{dmg:weapon_die+2d(resource{dado_de_combate})(perfurante)}, "
        "on_success{dmg:half}}} }",
    ),
    (
        "instant{ without{attack_roll}, target:creature, save{dex, "
        "cd=8+pb+wis_mod}, on_fail{ "
        "dmg:weapon_die+2d(resource{dado_de_combate})(forca) }, "
        "on_success{ dmg:half } }",
        "instant{ attack:replace{without{attack_roll}, target:creature, "
        "save{dex, cd=8+pb+wis_mod}, "
        "on_fail{dmg:weapon_die+2d(resource{dado_de_combate})(forca)}, "
        "on_success{dmg:half}} }",
    ),
    (
        "instant{ speed:roundup(speed/2), "
        "without{opportunity_attack} }",
        "instant{ move:roundup(speed/2)(without{opportunity_attack}) }",
    ),
    (
        "instant{ move:rounddown(walk/2), "
        "without{opportunity_attack} }",
        "instant{ move:rounddown(walk/2)(without{opportunity_attack}) }",
    ),
    (
        "dmg:3d6(cortante), without{crit_mult}, on_success:half",
        "dmg:3d6(cortante)(without{crit_mult}), on_success:half",
    ),
    (
        "on_fail{ without{verbal}, without{somatic}, "
        "duration:until_turn_start }",
        "on_fail{ modifiers{without{verbal}, without{somatic}}, "
        "duration:until_turn_start }",
    ),
    (
        "while_active{ requires:{magic.dmg:psiquico | "
        "magic.apply:{amedrontado | enfeiticado}}, without{verbal}, "
        "without{somatic}, resource_cost:{ pontos_de_feiticaria:spell_level | "
        "without{slot} } }",
        "while_active{ requires:{magic.dmg:psiquico | "
        "magic.apply:{amedrontado | enfeiticado}}, "
        "cast.modifiers{without{verbal}, without{somatic}, without{slot}}, "
        "resource_cost:pontos_de_feiticaria:spell_level }",
    ),
    (
        "while_active{ convert_dmg_type:pick:{grimorio}, ritual, "
        "without{ritual_time} }",
        "while_active{ convert_dmg_type:pick:{grimorio}, "
        "ritual(without{ritual_time}) }",
    ),
    (
        "on:cast{escola:{conjuracao | necromancia}} -> "
        "without{verbal}, without{somatic}, without{material}",
        "on:cast{escola:{conjuracao | necromancia}} -> "
        "modifiers{without{verbal}, without{somatic}, without{material}}",
    ),
    (
        "while_active{ duration:10, without{concentration}, aoe{",
        "while_active{ duration:10(without{concentration}), aoe{",
    ),
    (
        "while_active{ suppress{restriction{spellcasting}}, "
        "without{material(consumed)}, focus:self, "
        "suppress{restriction{somatic}}, suppress{restriction{verbal}} }",
        "while_active{ spellcasting.modifiers{"
        "suppress{restriction{spellcasting}}, "
        "without{material(consumed)}, focus:self, "
        "suppress{restriction{somatic}}, "
        "suppress{restriction{verbal}}} }",
    ),
    (
        "heal:dados_de_vida+con_mod, without{spend}",
        "heal:dados_de_vida+con_mod(without{spend})",
    ),
    (
        "instant{ trigger=ability{<armadilha_da_linha>, classe:cacador}, "
        "without{cost:detonate} }",
        "instant{ trigger=ability{<armadilha_da_linha>, classe:cacador}"
        "(without{cost:detonate}) }",
    ),
    (
        "instant{roll:1d6,without{cost:inspiracao_bardica}}",
        "instant{roll:1d6(without{cost:inspiracao_bardica})}",
    ),
    (
        "instant{ without{opportunity_attack:from{ target }} }",
        "instant{ move:triggering("
        "without{opportunity_attack:from{target}}) }",
    ),
    (
        "instant{ move:+5ft, without{opportunity_attack} }",
        "instant{ move:+5ft(without{opportunity_attack}) }",
    ),
    (
        "instant{ cast{ spell:invocar-mortos-vivos, "
        "modifiers{ action:bonus_action, forma:putrida } }, "
        "resource_cost:surto_selvagem:1(without{activate}), "
        "modifiers{without{material}} }",
        "instant{ cast{ spell:invocar-mortos-vivos, "
        "modifiers{action:bonus_action, forma:putrida, "
        "without{material}} }, "
        "resource_cost:surto_selvagem:1(without{activate}) }",
    ),
)


def attach_omissions(apps, schema_editor):
    model_names = (
        "TbClassehabilidade",
        "TbTalento",
        "TbOpcaojogo",
        "TbTracoracial",
    )
    for model_name in model_names:
        Model = apps.get_model("home", model_name)
        for obj in Model.objects.exclude(tags_json__isnull=True).iterator():
            old_tags = list(obj.tags_json or [])
            new_tags = []
            for tag in old_tags:
                text = str(tag)
                if (
                    model_name == "TbTracoracial"
                    and obj.nome == "Evolução Sybaris"
                    and text == "without{opportunity_attack}"
                ):
                    continue
                for old, new in REPLACEMENTS:
                    text = text.replace(old, new)
                text = text.replace(",  }", " }")
                new_tags.append(text)
            if new_tags != old_tags:
                obj.tags_json = new_tags
                obj.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0082_normalize_need_properties"),
    ]

    operations = [
        migrations.RunPython(attach_omissions, migrations.RunPython.noop),
    ]
