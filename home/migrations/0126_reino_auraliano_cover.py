from django.db import migrations


# The realm hero in ref/READ-ME CODEX.docx (image53.png) uses this same artwork.
# Keep Auralon's own image record untouched.
REALM_COVER = 'assets/world/reino-auraliano.png'


def assign_realm_cover(apps, schema_editor):
    territory_model = apps.get_model('home', 'TbTerritorio')
    territory = territory_model.objects.filter(slug='reino-auraliano').first()
    if territory and not (territory.imagem_url or '').strip():
        territory.imagem_url = REALM_COVER
        territory.save(update_fields=['imagem_url'])


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0125_race_image_focus'),
    ]

    operations = [
        migrations.RunPython(assign_realm_cover, migrations.RunPython.noop),
    ]
