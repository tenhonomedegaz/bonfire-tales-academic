from django.db import migrations


TERRITORY_COVERS = {
    'floresta-eterna': 'assets/world/floresta-eterna.png',
    'reino-de-agrabbar': 'assets/world/reino-de-agrabbar.png',
    'reino-eryndor': 'assets/world/reino-eryndor.png',
}


def assign_territory_covers(apps, schema_editor):
    territory_model = apps.get_model('home', 'TbTerritorio')
    for slug, cover in TERRITORY_COVERS.items():
        territory = territory_model.objects.filter(slug=slug).first()
        if territory and not (territory.imagem_url or '').strip():
            territory.imagem_url = cover
            territory.save(update_fields=['imagem_url'])


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0126_reino_auraliano_cover'),
    ]

    operations = [
        migrations.RunPython(assign_territory_covers, migrations.RunPython.noop),
    ]
