from django.db import migrations, models


POLICY = "suppress:pick{talento_racial, source:raca}"
OLD_POLICY = "always_active{ %s }" % POLICY


def move_policy_to_essence(apps, schema_editor):
    Essence = apps.get_model("home", "TbEssencia")
    RacialTrait = apps.get_model("home", "TbTracoracial")

    essence = Essence.objects.filter(slug="vampirismo").first()
    if essence is None:
        return

    essence_tags = list(essence.tags_json or [])
    if POLICY not in essence_tags:
        essence.tags_json = [*essence_tags, POLICY]
        essence.save(update_fields=["tags_json"])

    for trait in RacialTrait.objects.filter(id_essencia=essence):
        old_tags = list(trait.tags_json or [])
        new_tags = [tag for tag in old_tags if tag != OLD_POLICY]
        if new_tags != old_tags:
            trait.tags_json = new_tags
            trait.save(update_fields=["tags_json"])


class Migration(migrations.Migration):
    dependencies = [
        ("home", "0071_generalize_medium_armor_mastery"),
    ]

    operations = [
        migrations.AddField(
            model_name="tbessencia",
            name="tags_json",
            field=models.JSONField(
                blank=True,
                db_column="TagsJSON",
                default=list,
                help_text=(
                    "Politicas mecanicas da essencia. Toda maldicao deve declarar "
                    "suppress:pick{talento_racial, source:raca}."
                ),
            ),
        ),
        migrations.RunPython(
            move_policy_to_essence,
            migrations.RunPython.noop,
        ),
    ]
