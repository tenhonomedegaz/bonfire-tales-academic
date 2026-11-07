from django.db import migrations


def seed_policy(apps, schema_editor):
    options = apps.get_model('home', 'TbOpcaojogo')
    options.objects.using(schema_editor.connection.alias).get_or_create(
        slug='progressao-epic-boon', defaults={
            'nome': 'Epic Boon', 'tipo': 'Marco de Progressao',
            'descricao': 'Ao completar 160 aventuras e 20 niveis de classe, escolha um talento epico.',
            'tags_json': ['progression{adventures:160,level:20}', 'pick:talento:1(tipo:epico)'],
        })


class Migration(migrations.Migration):
    dependencies = [('home', '0161_tbtalento_epic_category')]
    operations = [migrations.RunPython(seed_policy, migrations.RunPython.noop)]
