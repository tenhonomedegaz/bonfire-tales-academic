from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0089_qa_character_rule_fixes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='badges_derivadas_ocultas',
            field=models.JSONField(
                blank=True,
                db_column='BadgesDerivadasOcultas',
                default=list,
                help_text='Badges automáticas opcionais que o usuário decidiu ocultar. Equipe nunca é ocultável.',
            ),
        ),
    ]
