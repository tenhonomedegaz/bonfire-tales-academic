from django.db import migrations


OLD_TAG = "adv:int_check(scope:{identificar_ilusao|recall_info})"
NEW_TAG = "adv:int_check(action:study)"


def generalize_keen_mind_context(apps, schema_editor):
    Talent = apps.get_model("home", "TbTalento")
    for talent in Talent.objects.filter(slug="mente-afiada"):
        tags = list(talent.tags_json or [])
        updated = [NEW_TAG if tag == OLD_TAG else tag for tag in tags]
        if updated != tags:
            talent.tags_json = updated
            talent.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0066_cleanup_nonmechanical_tags"),
    ]

    operations = [
        migrations.RunPython(
            generalize_keen_mind_context,
            migrations.RunPython.noop,
        ),
    ]
