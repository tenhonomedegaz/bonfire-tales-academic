from django.db import migrations, models


def _has_epic_label(labels):
    return "epico" in {
        label.strip().casefold() for label in (labels or "").split(",")
    }


def forwards(apps, schema_editor):
    talents = apps.get_model("home", "TbTalento").objects.using(
        schema_editor.connection.alias
    )
    for pk, labels in talents.filter(tipo="geral").values_list(
        "pk", "etiquetas_adicionais"
    ).iterator():
        if _has_epic_label(labels):
            talents.filter(pk=pk, tipo="geral").update(tipo="epico")


def backwards(apps, schema_editor):
    talents = apps.get_model("home", "TbTalento").objects.using(
        schema_editor.connection.alias
    )
    for pk, labels in talents.filter(tipo="epico").values_list(
        "pk", "etiquetas_adicionais"
    ).iterator():
        # New category-only epics must remain recognizable by the old code.
        values = {"tipo": "geral"}
        if not _has_epic_label(labels):
            values["etiquetas_adicionais"] = (
                f"{labels},epico" if labels else "epico"
            )
        talents.filter(pk=pk, tipo="epico").update(**values)


class Migration(migrations.Migration):
    dependencies = [("home", "0160_tbfeitolenda")]

    operations = [
        migrations.AlterField(
            model_name="tbtalento",
            name="tipo",
            field=models.CharField(
                choices=[("origem", "Origem"), ("geral", "Geral"), ("epico", "Épico")],
                db_column="Tipo",
                default="geral",
                max_length=50,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
