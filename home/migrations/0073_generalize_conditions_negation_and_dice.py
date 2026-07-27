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

NO_HEAD_RE = re.compile(r"(?<![a-z0-9_])no_([a-z0-9_]+)")
RESOURCE_DICE_RE = re.compile(
    r"(?<![a-z0-9_])(dado_de_cacador|dado_de_combate|dado_de_furtividade)"
    r"(?![a-z0-9_])"
)

EXACT_REPLACEMENTS = (
    (
        "on_fail: apply:possuido(self, mode:frenesi)",
        "on_fail: activate:ability{frenesi_de_sangue, essencia:vampirismo}(target:self)",
    ),
    (
        "while:frenesi{restriction{acoes_refinadas}, "
        "force:attack(profile:mordida_vampirica, target:nearest_living)}",
        "while:in:ability{frenesi_de_sangue, essencia:vampirismo}"
        "{restricts{acoes_refinadas}, "
        "force:attack(profile:mordida_vampirica, target:nearest_living)}",
    ),
    (
        "on:resource{dados_de_vida}>half -> cleanse:frenesi",
        "on:resource{dados_de_vida}>half -> "
        "end:ability{frenesi_de_sangue, essencia:vampirismo}",
    ),
    (
        "cond_immune:frenesi_de_sangue",
        "immune_ability{ability{frenesi_de_sangue, essencia:vampirismo}}",
    ),
    (
        "apply:debilitante(duration:until_next_turn_end, auto_fail)",
        "activate:opcao{estilo_debilitante}"
        "(duration:until_next_turn_end, save:auto_fail)",
    ),
    (
        "apply:marca_guardiao(target, duration:until_turn_start)",
        "mark{marca_guardiao, target:target, duration:until_turn_start}",
    ),
    (
        "instant{ apply:mutagenico(target:self) }",
        "instant{ activate:defined{mutagenico_preparado}(target:self, pick:1) }",
    ),
    (
        "cleanse:mutagenico(all)",
        "end:defined{mutagenico_preparado}(target:self, all)",
    ),
    (
        "requires:active{mutagenico}",
        "requires:active{defined{mutagenico_preparado}}",
    ),
    (
        "suppress:mutagenico.efeito_colateral(pick:1)",
        "suppress:active{defined{mutagenico_preparado}}"
        ".efeito_colateral(pick:1)",
    ),
    (
        "cleanse:mutagenico(pick:1), apply:mutagenico(target:self, pick:1)",
        "end:defined{mutagenico_preparado}(target:self, pick:1), "
        "activate:defined{mutagenico_preparado}(target:self, pick:1)",
    ),
    (
        "apply:incorporeo(self, duration:until_turn_end), ",
        "",
    ),
    (
        "apply:half_speed(",
        "speed:half(",
    ),
    (
        "apply:enlarge(",
        "size:+1(",
    ),
    (
        "apply:in_receptaculo(self, duration:120*pb_minutos)",
        "activate:ability{receptaculo_do_genio, classe:mistico}"
        "(target:self, duration:120*pb_minutos)",
    ),
    (
        "cleanse:in_receptaculo(self)",
        "end:ability{receptaculo_do_genio, classe:mistico}(target:self)",
    ),
    (
        "apply:seduzido(duration:until_next_turn_start, save:none)",
        "activate:ability{segredos_sybaris, essencia:vampirismo}"
        "(duration:until_next_turn_start, save:none)",
    ),
    (
        "apply:restricao_de_acao(duration:10, "
        "repeat_save:{turn_end,take_damage})",
        "apply:restringido(duration:10, repeat_save:{turn_end,take_damage})",
    ),
    (
        "apply:restricao_de_acao(escolhe 1: mover | acao | bonus_action, "
        "duration:proximo_turno)",
        "restricts{action:all_except{pick:1{move | action | bonus_action}}, "
        "duration:proximo_turno}",
    ),
    (
        "cleanse:vibracoes_letais",
        "mark{vibracoes_letais, remove:all}",
    ),
    (
        "cond_immune:afastado",
        "immune_effect:push",
    ),
    (
        "apply:afastado(duration:10, end_on:take_damage), "
        "restriction{ no_reactions }",
        "duration:10, end_on:take_damage, "
        "force:dash(target:away_from:self), "
        "restricts{reaction, move:toward:self, action}, "
        "grant:action{escape | dodge(unless:route_exists)}",
    ),
    (
        "apply:afastado(duration:10, end_on:take_damage), apply:no_reaction",
        "duration:10, end_on:take_damage, "
        "force:dash(target:away_from:self), "
        "restricts{reaction, move:toward:self, action}, "
        "grant:action{escape | dodge(unless:route_exists)}",
    ),
    (
        "apply:{ no_teleport, no_invisivel, no_telepathy }(target)",
        "restricts{teleport, condition{invisivel}, telepathy, target:target}",
    ),
)

RESTRICTION_REPLACEMENTS = {
    "reaction": "reaction",
    "reactions": "reaction",
    "heal": "heal",
    "camuflagem": "hide",
    "invisivel": "condition{invisivel}",
    "bonus_action": "action:bonus_action",
}


def _balanced_end(text, start):
    pairs = {"(": ")", "{": "}", "[": "]"}
    opening = text[start]
    closing = pairs[opening]
    depth = 0
    for pos in range(start, len(text)):
        char = text[pos]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return pos + 1
    return start


def _convert_restriction_states(text):
    for legacy, capability in RESTRICTION_REPLACEMENTS.items():
        pattern = re.compile(
            r"\bapply\s*:\s*no_" + re.escape(legacy)
            + r"(?:\(([^()]*)\))?"
        )

        def replace_apply(match):
            args = (match.group(1) or "").strip()
            body = capability + (", " + args if args else "")
            return "restricts{%s}" % body

        text = pattern.sub(replace_apply, text)

        pattern = re.compile(
            r"(?<![a-z0-9_:])no_" + re.escape(legacy)
            + r"(?:\(([^()]*)\))?"
        )

        def replace_standalone(match):
            args = (match.group(1) or "").strip()
            body = capability + (", " + args if args else "")
            return "restricts{%s}" % body

        text = pattern.sub(replace_standalone, text)
    return text


def _convert_no_prefixes(text):
    out = []
    cursor = 0
    while True:
        match = NO_HEAD_RE.search(text, cursor)
        if not match:
            out.append(text[cursor:])
            return "".join(out)

        out.append(text[cursor:match.start()])
        end = match.end()
        if end < len(text) and text[end] == ":":
            pos = end + 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            value = re.match(r"[a-z0-9_]+", text[pos:])
            if value:
                pos += value.end()
            if pos < len(text) and text[pos] in "({[":
                pos = _balanced_end(text, pos)
            end = pos
        elif end < len(text) and text[end] in "({[":
            end = _balanced_end(text, end)

        operand = match.group(1) + text[match.end():end]
        if NO_HEAD_RE.search(operand):
            operand = _convert_no_prefixes(operand)
        out.append("without{%s}" % operand)
        cursor = end


def _resource_dice_refs(text):
    def replace(match):
        prefix = text[:match.start()]
        if re.search(r"(?:resource|define)\s*\{\s*$", prefix):
            return match.group(1)
        return "resource{%s}" % match.group(1)

    return RESOURCE_DICE_RE.sub(replace, text)


def _split_top_level(value):
    parts = []
    start = 0
    stack = []
    pairs = {")": "(", "}": "{", "]": "["}
    for pos, char in enumerate(value):
        if char in "({[":
            stack.append(char)
        elif char in ")}]":
            if stack and stack[-1] == pairs[char]:
                stack.pop()
        elif char == "," and not stack:
            parts.append(value[start:pos].strip())
            start = pos + 1
    parts.append(value[start:].strip())
    return [part for part in parts if part]


def _separate_devil_sight(text):
    marker = "sense:darkvision("
    cursor = 0
    out = []
    while True:
        start = text.find(marker, cursor)
        if start < 0:
            out.append(text[cursor:])
            return "".join(out)
        args_start = start + len(marker) - 1
        end = _balanced_end(text, args_start)
        if end == args_start:
            out.append(text[cursor:])
            return "".join(out)

        args = text[args_start + 1:end - 1]
        magical = "escuridao_magica" in args or re.search(
            r"(?:^|,\s*)magical(?:\s*,|$)", args
        )
        if not magical:
            out.append(text[cursor:end])
            cursor = end
            continue

        kept = [
            part for part in _split_top_level(args)
            if "escuridao_magica" not in part and part != "magical"
        ]
        range_args = [
            part for part in kept
            if part.startswith(("range:", "radius:"))
        ]
        darkvision = "sense:darkvision"
        if kept:
            darkvision += "(" + ", ".join(kept) + ")"
        devilsight = "sense:devilsight"
        if range_args:
            devilsight += "(" + ", ".join(range_args) + ")"

        qualifier = ""
        qualified_end = end
        if end < len(text) and text[end] == "{":
            qualified_end = _balanced_end(text, end)
            qualifier = text[end:qualified_end]

        out.append(text[cursor:start])
        out.append(
            darkvision + qualifier + ", " + devilsight + qualifier
        )
        cursor = qualified_end


def rewrite_tag(tag):
    text = str(tag)
    for old, new in EXACT_REPLACEMENTS:
        text = text.replace(old, new)
    text = _convert_restriction_states(text)
    text = _convert_no_prefixes(text)
    text = _resource_dice_refs(text)
    text = _separate_devil_sight(text)
    return text


def generalize_tags(apps, schema_editor):
    for model_name in TAG_MODELS:
        Model = apps.get_model("home", model_name)
        for obj in Model.objects.exclude(tags_json__isnull=True).iterator():
            old_tags = list(obj.tags_json or [])
            new_tags = [rewrite_tag(tag) for tag in old_tags]
            if new_tags != old_tags:
                obj.tags_json = new_tags
                obj.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0072_move_curse_pick_policy_to_essence"),
    ]

    operations = [
        migrations.RunPython(
            generalize_tags,
            migrations.RunPython.noop,
        ),
    ]
