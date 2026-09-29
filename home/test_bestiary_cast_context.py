from django.test import SimpleTestCase

from .management.commands.importar_bestiario_csv import _split_secao


CATALOG = [
    {'en_lower': name.lower(), 'slug': slug, 'name_en': name,
     'name_pt': name, 'resolved': True}
    for name, slug in (
        ('Mirror Image', 'imagem-espelhada'),
        ('Dispel Evil and Good', 'dissipar-o-mal-e-o-bem'),
        ('Light', 'luz'), ('Fly', 'voo'), ('Fireball', 'bola-de-fogo'),
        ('Wish', 'desejo'),
    )
]


class CastContextTests(SimpleTestCase):
    def test_spell_mentioned_as_countermeasure_is_reference_not_cast(self):
        block = _split_secao(
            'Inhabit Object. The shard can be forced out by a Dispel Evil and Good spell.',
            CATALOG)[0]
        self.assertEqual([ref['slug'] for ref in block['spell_refs']],
                         ['dissipar-o-mal-e-o-bem'])
        self.assertNotIn('tags', block)

    def test_cast_spell_survives_while_light_condition_does_not_become_cast(self):
        block = _split_secao(
            'Phantasms. The cloaker casts the Mirror Image spell. '
            'The spell ends if it enters Bright Light.', CATALOG)[0]
        self.assertEqual(block['tags'], ['cast{spell:imagem-espelhada}'])
        self.assertEqual({ref['slug'] for ref in block['spell_refs']},
                         {'imagem-espelhada'})

    def test_flight_description_is_not_the_fly_spell(self):
        block = _split_secao(
            'Flight. The shard can fly using its own flying speed.', CATALOG)[0]
        self.assertNotIn('tags', block)
        self.assertNotIn('spell_refs', block)

    def test_prepared_spell_list_remains_castable(self):
        block = _split_secao(
            'Spellcasting. The mage prepares these spells: Fireball, Fly, Light.',
            CATALOG)[0]
        self.assertEqual(set(block['tags']),
                         {'cast{spell:bola-de-fogo}', 'cast{spell:voo}', 'cast{spell:luz}'})

    def test_actual_cast_outside_spellcasting_remains_castable(self):
        block = _split_secao(
            'Arcane Burst. The mage casts Fireball at a creature it can see.',
            CATALOG)[0]
        self.assertEqual(block['tags'], ['cast{spell:bola-de-fogo}'])

    def test_explicit_frequency_list_keeps_uses_and_cast_tags(self):
        block = _split_secao('Innate Magic. At will: Fly, Light.', CATALOG)[0]
        self.assertEqual([ref['slug'] for ref in block['spell_uses'][0]['spells']],
                         ['voo', 'luz'])
        self.assertEqual(set(block['tags']),
                         {'cast{spell:voo, at-will}', 'cast{spell:luz, at-will}'})

    def test_named_spell_can_be_referenced_without_being_cast(self):
        block = _split_secao(
            "Life Eater. The victim can't be revived except by a Wish spell.",
            CATALOG)[0]
        self.assertEqual([ref['slug'] for ref in block['spell_refs']], ['desejo'])
        self.assertNotIn('tags', block)

    def test_cannot_cast_is_not_a_cast_tag(self):
        block = _split_secao(
            "Silence. The mage can't cast Fireball while silenced.",
            CATALOG)[0]
        self.assertNotIn('spell_refs', block)
        self.assertNotIn('tags', block)
