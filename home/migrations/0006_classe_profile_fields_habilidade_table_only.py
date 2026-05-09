from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0005_tbtalento_etiquetas_adicionais_pre_requisito"),
    ]

    operations = [
        migrations.AddField(
            model_name="tbclasse",
            name="atributo_principal",
            field=models.TextField(blank=True, db_column="AtributoPrincipal", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="dado_vida",
            field=models.TextField(blank=True, db_column="DadoVida", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="pv_nivel_1",
            field=models.TextField(blank=True, db_column="PVNivel1", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="pv_por_nivel",
            field=models.TextField(blank=True, db_column="PVPORNivel", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="resistencias",
            field=models.TextField(blank=True, db_column="Resistencias", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="pericias",
            field=models.TextField(blank=True, db_column="Pericias", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="armas",
            field=models.TextField(blank=True, db_column="Armas", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="ferramentas",
            field=models.TextField(blank=True, db_column="Ferramentas", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="armaduras",
            field=models.TextField(blank=True, db_column="Armaduras", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="equipamento",
            field=models.TextField(blank=True, db_column="Equipamento", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="multiclass_requisitos",
            field=models.TextField(blank=True, db_column="MulticlassRequisitos", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="multiclass_pericias",
            field=models.TextField(blank=True, db_column="MulticlassPericias", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="multiclass_ferramentas",
            field=models.TextField(blank=True, db_column="MulticlassFerramentas", null=True),
        ),
        migrations.AddField(
            model_name="tbclasse",
            name="multiclass_armaduras",
            field=models.TextField(blank=True, db_column="MulticlassArmaduras", null=True),
        ),
        migrations.AddField(
            model_name="tbclassehabilidade",
            name="table_only",
            field=models.BooleanField(db_column="TableOnly", default=False, help_text="Mostra esta habilidade apenas na tabela de progressao."),
        ),
    ]
