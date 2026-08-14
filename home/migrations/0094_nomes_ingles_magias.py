from django.db import migrations


SPELL_NAMES = {
    'alarme': 'Alarm',
    'cerimonia': 'Ceremony',
    'compreender-idiomas': 'Comprehend Languages',
    'detectar-magia': 'Detect Magic',
    'detectar-veneno-e-doenca': 'Detect Poison and Disease',
    'disco-flutuante': "Tenser's Floating Disk",
    'encontrar-familiar': 'Find Familiar',
    'escrita-ilusoria': 'Illusory Script',
    'falar-com-animais': 'Speak with Animals',
    'fios-prateados': 'Silvery Barbs',
    'identificar': 'Identify',
    'purificar-comida-e-bebida': 'Purify Food and Drink',
    'servo-invisivel': 'Unseen Servant',
    'alterar-se': 'Alter Self',
    'augurio': 'Augury',
    'boca-magica': 'Magic Mouth',
    'bolso-de-pulso': 'Wristpocket',
    'conhecimento-emprestado': 'Borrowed Knowledge',
    'definhar-e-florescer': 'Wither and Bloom',
    'disparo-cinetico': "Kinetic Jaunt",
    'escrita-celeste': 'Skywrite',
    'homunculos-servicais': 'Unseen Servants',
    'localizar-animais-ou-plantas': 'Locate Animals or Plants',
    'mensageiro-animal': 'Animal Messenger',
    'repouso-gentil': 'Gentle Repose',
    'sentido-bestial': 'Beast Sense',
    'servo-homunculo': 'Homunculus Servant',
    'silencio': 'Silence',
    'sussurro-dissolvente': 'Unraveling Whisper',
    'vortice-distorcido': 'Vortex Warp',
    'andar-sobre-agua': 'Water Walk',
    'cabana-minuscula': "Leomund's Tiny Hut",
    'cantico-amaldicoado': 'Cursed Chant',
    'corcel-fantasma': 'Phantom Steed',
    'mesclar-se-a-pedra': 'Meld into Stone',
    'respirar-na-agua': 'Water Breathing',
    'simular-morte': 'Feign Death',
    'adivinhacao': 'Divination',
    'comunhao': 'Commune',
    'comunhao-com-a-natureza': 'Commune with Nature',
    'contato-extraplanar': 'Contact Other Plane',
    'ligacao-telepatica': "Rary's Telepathic Bond",
    'voragem': 'Maelstrom',
    'conjurar-fada': 'Summon Fey',
    'intermedio': 'Forbiddance',
    'invocacao-objeto': "Drawmij's Instant Summons",
    'conjurar-celestial': 'Summon Celestial',
    'estupefacao': 'Feeblemind',
}


def fill_spell_names(apps, schema_editor):
    Magia = apps.get_model('home', 'TbMagia')
    for slug, english_name in SPELL_NAMES.items():
        Magia.objects.filter(slug=slug).update(nome_ingles=english_name)


def clear_spell_names(apps, schema_editor):
    Magia = apps.get_model('home', 'TbMagia')
    Magia.objects.filter(slug__in=SPELL_NAMES).update(nome_ingles=None)


class Migration(migrations.Migration):
    dependencies = [('home', '0093_conteudo_reuniao_e_imagens_racas')]

    operations = [migrations.RunPython(fill_spell_names, clear_spell_names)]
