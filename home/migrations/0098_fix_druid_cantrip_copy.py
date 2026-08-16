from django.db import migrations


BAD_CANTRIP_LINKS = (
    '[truques adicionais](tbClassehabilidade, o-celestial, truques-adicionais)',
    '[Truques Adicionais](tbClassehabilidade, o-celestial, truques-adicionais)',
)

CANTRIP_SWAP_RULE = (
    'Sempre que ganhar um nível de Druida, você pode substituir um truque de Druida '
    'que conhece por outro truque da Lista de Magias de Druida.'
)


def fix_druid_copy(apps, schema_editor):
    Classe = apps.get_model('home', 'TbClasse')
    Feature = apps.get_model('home', 'TbClassehabilidade')
    druid = Classe.objects.filter(slug='druida').first()
    if druid is None:
        return
    for feature in Feature.objects.filter(id_classe=druid):
        description = feature.descricao or ''
        updated = description
        for bad_link in BAD_CANTRIP_LINKS:
            updated = updated.replace(bad_link, 'truques adicionais')
        if (feature.nome == 'Conjuração Druídica'
                and 'substituir um truque de Druida' not in updated):
            updated = updated.rstrip() + '\n\n' + CANTRIP_SWAP_RULE
        if updated != description:
            feature.descricao = updated
            feature.save(update_fields=['descricao'])


class Migration(migrations.Migration):

    dependencies = [
        ('home', '0097_character_build_revisions'),
    ]

    operations = [
        migrations.RunPython(fix_druid_copy, migrations.RunPython.noop),
    ]
