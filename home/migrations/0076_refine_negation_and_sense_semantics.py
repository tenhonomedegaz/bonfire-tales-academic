import re

from django.db import migrations


TAG_MODELS = (
    "TbClassehabilidade",
    "TbTalento",
    "TbOpcaojogo",
    "TbTracoracial",
    "TbClasse",
    "TbAntecedente",
    "TbMagia",
    "TbBestiario",
    "TbItemMundano",
    "TbItemMagico",
    "TbEssencia",
)


EXACT_REPLACEMENTS = (
    (
        "requires:{adv | ally(range:5ft) and without{dadv}}",
        "requires:{adv | ally(range:5ft) and not{dadv}}",
    ),
    (
        "requires:{ target(range:5ft) and without{dadv} and "
        "without{other_creature(range:5ft)} }",
        "requires:{ target(range:5ft) and not{dadv} and "
        "not{other_creature(range:5ft)} }",
    ),
    (
        "requires:without{incapacitado}",
        "requires:not{condition{incapacitado, target:self}}",
    ),
    (
        "requires:without{inconsciente}",
        "requires:not{condition{inconsciente, target:self}}",
    ),
    (
        "apply:cego(requires:without{magic_darkvision})",
        "apply:cego(restriction{sense:devilsight})",
    ),
    (
        "restriction{ without{attack_target}, without{cast_target}, "
        "without{dmg_target} }",
        "restriction{attack_target | cast_target | dmg_target}",
    ),
    (
        "restriction{ without{target:morto_vivo}, "
        "without{target:construto} }",
        "restriction{target:creature_type{morto_vivo | construto}}",
    ),
    (
        "restriction{ without{cover} }",
        "suppress{cover}",
    ),
    (
        "restriction{without{mascara_da_piedade}}",
        "restriction{not{equipped{mascara_da_piedade}}}",
    ),
    (
        "restriction{ without{space} }",
        "restriction{not{space:available}}",
    ),
    (
        "if(without{space}):reroll",
        "if(not{space:available}):reroll",
    ),
    (
        "unless(classlvl>=8): without{fly}",
        "restriction{move:fly, unless:classlvl>=8}",
    ),
    (
        "if:without{food}",
        "if:not{food}",
    ),
    (
        "speed:without{reduce}",
        "speed.ignore:reduction",
    ),
    (
        "companion.without{resist}",
        "companion.ignore:resist",
    ),
    (
        "weapon.without{resist:{concussao, cortante, perfurante}}",
        "weapon.ignore:resist:{concussao, cortante, perfurante}",
    ),
    (
        "resource_cost:{ surto_selvagem:1 | without{effect} }"
        "(without{material})",
        "resource_cost:surto_selvagem:1(without{activate}), "
        "modifiers{without{material}}",
    ),
    (
        "apply:enfeiticado(without{percepcao})",
        "apply:enfeiticado("
        "suppress{detect{components:[verbal, somatic], source:self}}, "
        "suppress{memory{duration:effect, target:target}}"
        ")",
    ),
    (
        "without{stack:catalisador_da_ca}çada",
        "limit{effect:opcao{catalisador_da_cacada}, max:1}",
    ),
    (
        "sense:darkvision(120ft, duration:1d20h, else:devilsight)",
        "if(has:sense{darkvision}): "
        "sense:devilsight(range:120ft, duration:1d20h) "
        "else: sense:darkvision(range:120ft, duration:1d20h)",
    ),
)


NOT_IDENTIFIERS = {
    "not_dead": "not{dead}",
    "not_incapacitated": "not{condition{incapacitado}}",
    "not_inconsciente": "not{condition{inconsciente}}",
    "not_instant_death": "not{death{instant}}",
    "not_moved": "not{moved}",
    "not_possuido": "not{condition{possuido}}",
    "not_prof": "not{prof}",
    "not_self": "not{self}",
    "not_sustained": "not{sustained}",
    "not_target": "not{target}",
    "not_used": "not{used}",
}


def _balanced_end(text, start):
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos + 1
    return start


def _without_semantics(operand):
    stripped = operand.strip()
    lowered = stripped.lower()

    if re.match(r"^(?:adv|dadv)\b", lowered):
        return "suppress{%s}" % stripped
    if lowered.startswith("difficult_terrain"):
        return "ignore:%s" % stripped
    if lowered.startswith("passive_perception_penalty"):
        suffix = stripped[len("passive_perception_penalty"):]
        return "suppress{penalty:passive_perception%s}" % suffix
    if lowered.startswith("penalty:"):
        return "suppress{%s}" % stripped
    if lowered.startswith("restriction:"):
        return "suppress{restriction{%s}}" % stripped.split(":", 1)[1]
    if lowered == "somatic_restriction":
        return "suppress{restriction{somatic}}"
    if lowered == "verbal_restriction":
        return "suppress{restriction{verbal}}"
    if lowered.startswith("concentration_break_on_damage"):
        suffix = stripped[len("concentration_break_on_damage"):]
        return "suppress{concentration_break(on:damage%s)}" % suffix
    if lowered.startswith("stack:"):
        return "limit{effect:%s, max:1}" % stripped.split(":", 1)[1]
    if lowered in {"breath", "breathe"}:
        return "need{air, enabled:false}"
    if lowered == "eat":
        return "need{food, enabled:false}"
    if lowered == "age":
        return "immune_effect:aging"
    if lowered == "sleep":
        return "need{sleep, enabled:false}"
    if lowered.startswith("sleep{from:magia}"):
        return "immune_effect:sleep(source:magia)"
    if lowered == "sustenance":
        return "need{sustenance, enabled:false}"
    if lowered.startswith("surprised"):
        suffix = stripped[len("surprised"):]
        return "immune_effect:surprise%s" % suffix
    if lowered.startswith("fall"):
        suffix = stripped[len("fall"):]
        return "immune_effect:fall%s" % suffix
    if lowered.startswith("forced_movement"):
        suffix = stripped[len("forced_movement"):]
        return "immune_effect:forced_movement%s" % suffix
    if lowered.startswith("disarm"):
        suffix = stripped[len("disarm"):]
        return "immune_effect:disarm%s" % suffix
    if lowered.startswith("resist"):
        return "ignore:%s" % stripped
    if lowered == "inconsciente":
        return "suppress{condition{inconsciente}, trigger:hp=0}"
    if lowered == "unconscious_at_0":
        return "suppress{condition{inconsciente}, trigger:hp=0}"
    if lowered == "target":
        return "immune_effect:targeting"
    if lowered == "teleport":
        return "restricts{teleport}"
    if lowered.startswith("trace"):
        return "suppress{%s}" % stripped
    if lowered.startswith("end_condition:"):
        return "suppress{%s}" % stripped
    if lowered == "magic_darkvision":
        return "not{sense:devilsight}"
    return "without{%s}" % stripped


def _rewrite_without(text):
    marker = "without{"
    out = []
    cursor = 0
    while True:
        start = text.find(marker, cursor)
        if start < 0:
            out.append(text[cursor:])
            return "".join(out)
        end = _balanced_end(text, start + len(marker) - 1)
        if end <= start:
            out.append(text[cursor:])
            return "".join(out)
        out.append(text[cursor:start])
        operand = text[start + len(marker):end - 1]
        operand = _rewrite_without(operand)
        out.append(_without_semantics(operand))
        cursor = end


def rewrite_tag(tag):
    text = str(tag)
    for old, new in EXACT_REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in NOT_IDENTIFIERS.items():
        text = re.sub(
            r"(?<![a-z0-9_])" + re.escape(old) + r"(?![a-z0-9_])",
            lambda _match, replacement=new: replacement,
            text,
        )
    return _rewrite_without(text)


def refine_negations(apps, schema_editor):
    for model_name in TAG_MODELS:
        Model = apps.get_model("home", model_name)
        for obj in Model.objects.exclude(tags_json__isnull=True).iterator():
            old_tags = list(obj.tags_json or [])
            new_tags = [rewrite_tag(tag) for tag in old_tags]
            if new_tags != old_tags:
                obj.tags_json = new_tags
                obj.save(update_fields=["tags_json"])


def _append_unique(tags, tag):
    if tag not in tags:
        tags.append(tag)


def refine_class_senses(apps, schema_editor):
    Ability = apps.get_model("home", "TbClassehabilidade")
    additions = {
        "Manto Umbral": (
            "while_active{ sense:darkvision(range:60ft, target:chosen), "
            "sense:devilsight(range:60ft, target:chosen), "
            "instant{dmg:cha_mod(psiquico, target:chosen)} }",
        ),
        "O Terceiro Olho": (
            "match(beneficio){ visao_infernal:{ "
            "sense:darkvision, sense:devilsight } }",
        ),
        "Manifestação Mística": (
            "define{visao_das_sombras: grant:bound{familiar, "
            "sense:darkvision(range:120ft), "
            "sense:devilsight(range:120ft)}}",
        ),
        "O Manto do Vazio": (
            "while_active{ aura{radius:60ft, target:{self|allies}, "
            "effects{sense:darkvision(range:60ft), "
            "sense:devilsight(range:60ft)}} }",
        ),
        "Pacto Umbral": (
            "sense:darkvision(range:120ft)",
            "sense:devilsight(range:120ft)",
        ),
    }
    for name, extra_tags in additions.items():
        for ability in Ability.objects.filter(nome=name):
            tags = list(ability.tags_json or [])
            if name == "Manto Umbral":
                tags = [
                    tag for tag in tags
                    if "sense:darkvision(range:60ft, target:chosen)" not in tag
                ]
            for tag in extra_tags:
                _append_unique(tags, tag)
            if tags != list(ability.tags_json or []):
                ability.tags_json = tags
                ability.save(update_fields=["tags_json"])


def refine_option_senses(apps, schema_editor):
    Option = apps.get_model("home", "TbOpcaojogo")
    for option in Option.objects.filter(nome="Óculos Escuro"):
        tags = [
            "always_active{ "
            "sense:darkvision(range:60ft), "
            "sense:devilsight(range:60ft), "
            "ignore:obscured{light | heavy}, "
            "adv:save(vs:cego) }"
        ]
        if tags != list(option.tags_json or []):
            option.tags_json = tags
            option.save(update_fields=["tags_json"])
    for option in Option.objects.filter(nome="Emanação de Escuridão"):
        tags = list(option.tags_json or [])
        _append_unique(
            tags,
            "while_active{ aura{target:{self|chosen}, "
            "effects{sense:darkvision, sense:devilsight}} }",
        )
        if tags != list(option.tags_json or []):
            option.tags_json = tags
            option.save(update_fields=["tags_json"])


BESTIARY_DEVILSIGHT_RE = re.compile(
    r"vis[aã]o no escuro\s+(\d+)\s*m\s*\((\d+)\s*ft\.?\)"
    r"\s*\(sem impedimento por escurid[aã]o m[aá]gica\)",
    re.IGNORECASE,
)


def refine_bestiary_senses(apps, schema_editor):
    Bestiary = apps.get_model("home", "TbBestiario")
    for creature in Bestiary.objects.all().iterator():
        description = creature.descricao_markdown or ""
        match = BESTIARY_DEVILSIGHT_RE.search(description)
        if not match:
            continue
        range_ft = match.group(2)
        tags = list(creature.tags_json or [])
        _append_unique(tags, "sense:darkvision(range:%sft)" % range_ft)
        _append_unique(tags, "sense:devilsight(range:%sft)" % range_ft)
        if tags != list(creature.tags_json or []):
            creature.tags_json = tags
            creature.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0075_split_magical_darkvision_from_devilsight"),
    ]

    operations = [
        migrations.RunPython(refine_negations, migrations.RunPython.noop),
        migrations.RunPython(refine_class_senses, migrations.RunPython.noop),
        migrations.RunPython(refine_option_senses, migrations.RunPython.noop),
        migrations.RunPython(refine_bestiary_senses, migrations.RunPython.noop),
    ]
