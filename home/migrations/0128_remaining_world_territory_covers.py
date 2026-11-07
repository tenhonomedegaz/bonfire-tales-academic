from django.db import migrations


TERRITORY_COVERS = {
    'reino-karag-dum': 'assets/world/reino-karag-dum.png',
    'reino-volgran': 'assets/world/reino-volgran.png',
    'territorio-independente': 'assets/world/territorio-independente.png',
    'vyrmrealm': 'assets/world/vyrmrealm.png',
    'zonas-de-perigo': 'assets/world/zonas-de-perigo.png',
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
        ('home', '0127_world_territory_covers'),
    ]

    operations = [
        migrations.RunPython(assign_territory_covers, migrations.RunPython.noop),
    ]
