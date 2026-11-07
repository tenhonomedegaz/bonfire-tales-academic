from django.db import migrations


REPLACEMENTS = {
    "need{air, enabled:false}": "need:air=false",
    "need{food, enabled:false}": "need:food=false",
    "need{water, enabled:false}": "need:water=false",
    "need{sleep, enabled:false}": "need:sleep=false",
    "need{sustenance, enabled:false}": "need:sustenance=false",
}


def normalize_needs(apps, schema_editor):
    model_names = (
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
    for model_name in model_names:
        Model = apps.get_model("home", model_name)
        for obj in Model.objects.exclude(tags_json__isnull=True).iterator():
            old_tags = list(obj.tags_json or [])
            new_tags = []
            for tag in old_tags:
                text = str(tag)
                for old, new in REPLACEMENTS.items():
                    text = text.replace(old, new)
                new_tags.append(text)
            if new_tags != old_tags:
                obj.tags_json = new_tags
                obj.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0081_add_darkvision_to_umbral_eyes"),
    ]

    operations = [
        migrations.RunPython(normalize_needs, migrations.RunPython.noop),
    ]
