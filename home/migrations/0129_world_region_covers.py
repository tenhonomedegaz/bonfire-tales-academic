from django.db import migrations


REGION_COVERS = {
    'agrabbar': 'assets/world/regions/agrabbar.png',
    'bastiao-rochaeterna': 'assets/world/regions/bastiao-rochaeterna.png',
    'brinvalde': 'assets/world/regions/brinvalde.png',
    'crystalis': 'assets/world/regions/crystalis.png',
    'drumhuldar': 'assets/world/regions/drumhuldar.png',
    'elenharis': 'assets/world/regions/elenharis.png',
    'elyrenna': 'assets/world/regions/elyrenna.png',
    'fjarnok': 'assets/world/regions/fjarnok.png',
    'floresta-eterna': 'assets/world/regions/floresta-eterna.png',
    'muralha-de-agramar': 'assets/world/regions/muralha-de-agramar.png',
    'porto-espolio': 'assets/world/regions/porto-espolio.png',
    'shaerelyn': 'assets/world/regions/shaerelyn.png',
    'solmarion': 'assets/world/regions/solmarion.png',
    'sylvereth': 'assets/world/regions/sylvereth.png',
    'terras-devastadas': 'assets/world/regions/terras-devastadas.png',
    'terras-ferteis': 'assets/world/regions/terras-ferteis.png',
    'thurvangar': 'assets/world/regions/thurvangar.png',
    'velaryn': 'assets/world/regions/velaryn.png',
    'vilaterra': 'assets/world/regions/vilaterra.png',
    'volgranndur': 'assets/world/regions/volgranndur.png',
    'vyrmhein': 'assets/world/regions/vyrmhein.png',
    'zarkantar': 'assets/world/regions/zarkantar.png',
}


def assign_region_covers(apps, schema_editor):
    region_model = apps.get_model('home', 'TbRegiao')
    for slug, cover in REGION_COVERS.items():
        region = region_model.objects.filter(slug=slug).first()
        if region and not (region.brasao_url or '').strip():
            region.brasao_url = cover
            region.save(update_fields=['brasao_url'])


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0128_remaining_world_territory_covers'),
    ]

    operations = [
        migrations.RunPython(assign_region_covers, migrations.RunPython.noop),
    ]
