import re
import unicodedata

from django.db import migrations


def _norm(value):
    return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()


def fix_qa_character_rules(apps, schema_editor):
    Trait = apps.get_model("home", "TbTracoracial")
    Feature = apps.get_model("home", "TbClassehabilidade")
    Talent = apps.get_model("home", "TbTalento")

    # Translate the legacy prose shape to the generic identity contract. This
    # intentionally matches any race adjective and leaves mixed/composite prose
    # untouched for a future explicit content retagging.
    legacy_group = re.compile(
        r"(?:^|;\s*)qualquer linhagem [a-z]+(?: ou essencia)?\.?$")
    for trait in Trait.objects.filter(talento_racial=True):
        prerequisite = _norm(trait.pre_requisito)
        match = legacy_group.search(prerequisite)
        if not match:
            continue
        required = ("character_prereq:any{lineage:*|essence:*}"
                    if " ou essencia" in match.group(0)
                    else "character_prereq:any{lineage:*}")
        tags = list(trait.tags_json or [])
        if required not in tags:
            tags.insert(0, required)
            trait.tags_json = tags
            trait.save(update_fields=["tags_json"])

    # Legacy prose of the shape "ganha proficiência em X, se ainda não ..." becomes the
    # generic replacement-pick contract, whatever the feature and skill are.
    proficiency = re.compile(
        r"ganha\s+\W*proficiencia em\s+\W*([a-z ]+?)\W*,\s*se ainda nao\b")
    skill_slugs = {
        "acrobacia", "adestrar-animais", "arcanismo", "atletismo", "atuacao",
        "enganacao", "furtividade", "historia", "intimidacao", "intuicao",
        "investigacao", "medicina", "natureza", "percepcao", "persuasao",
        "prestidigitacao", "religiao", "sobrevivencia",
    }
    for feature in Feature.objects.all():
        tags = list(feature.tags_json or [])
        if any(str(tag).startswith("pick:pericia:") for tag in tags):
            continue
        match = proficiency.search(_norm(feature.descricao))
        if match:
            skill = re.sub(r"\s+", "-", match.group(1).strip())
            if skill not in skill_slugs:
                continue
            tags.insert(0, "pick:pericia:1(replace:%s)" % skill)
            feature.tags_json = tags
            feature.save(update_fields=["tags_json"])

    # Repair the old inverted save-pick grammar for every talent that used it.
    old_save = re.compile(r"^save_prof:pick:(\{[^}]+\})(.*)$")
    for talent in Talent.objects.all():
        original = list(talent.tags_json or [])
        tags = []
        for tag in original:
            match = old_save.match(str(tag))
            tags.append("pick:save_prof:%s:1%s" % match.groups() if match else tag)
        if tags != original:
            talent.tags_json = tags
            talent.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0088_perfil_social_curtir_seguir"),
    ]

    operations = [
        migrations.RunPython(fix_qa_character_rules, migrations.RunPython.noop),
    ]
