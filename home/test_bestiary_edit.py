from copy import deepcopy

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import TbBestiario


class ImportedBestiaryEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bestiary_staff', password='test', is_staff=True)
        self.client.force_login(self.user)
        self.original = {
            'name': 'Unicórnio', 'size': 'Grande', 'type': 'Celestial',
            'cr': '5', 'ac': 12, 'hp': '97 (13d10 + 26)',
            'speed': '15 m (50 ft.)', 'str': 18, 'dex': 14, 'con': 15,
            'int': 11, 'wis': 17, 'cha': 16,
            'traits': [{'name': 'Resistência Lendária', 'entries': ['Resiste.'],
                        'name_en': 'Legendary Resistance', 'entries_en': ['Resists.']}],
            'actions': [{'name': 'Chifre', 'entries': ['Ataca.'], 'name_en': 'Horn'}],
            'reactions': [{'name': 'Escudo', 'entries': ['Defende.']}],
            'legendary_actions': [{'name': 'Cura', 'entries': ['Cura.']}],
            'damage_resistances': ['fogo'], 'spell_refs': ['cura'],
            'tags': ['criatura:celestial'],
        }
        self.creature = TbBestiario.objects.create(
            slug='unicornio-edit-test', nome='Unicórnio', tipo='Celestial',
            tamanho='Grande', nd='5', ca='12', pv='97 (13d10 + 26)',
            statblock_json=deepcopy(self.original), comunidade=False,
        )
        self.url = reverse('bestiario_editar', args=[self.creature.pk])

    def form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        pf = response.context['pf']
        return {
            **{key: str(value) for key, value in pf.items() if key != 'abil'},
            **{key: str(value) for key, value in pf['abil'].items()},
            'edit_token': response.context['edit_token'], 'oficial': 'on',
        }

    def test_unrelated_edit_keeps_imported_mechanics_and_custom_size(self):
        form = self.form()
        self.assertContains(self.client.get(self.url), 'value="Grande" selected')
        form['descricao'] = 'Nova descrição.'
        response = self.client.post(self.url, form)
        self.assertEqual(response.status_code, 302)
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.statblock_json, self.original)
        self.assertEqual(self.creature.pv, '97 (13d10 + 26)')
        self.assertEqual(self.creature.tamanho, 'Grande')
        self.assertEqual(self.creature.descricao_markdown, 'Nova descrição.')

    def test_tag_edit_keeps_english_and_other_ability_groups(self):
        form = self.form()
        form['tracos'] = 'Resistência Lendária | Resiste. | defesa:lenda'
        response = self.client.post(self.url, form)
        self.assertEqual(response.status_code, 302)
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.statblock_json['traits'][0]['tags'], ['defesa:lenda'])
        self.assertEqual(self.creature.statblock_json['traits'][0]['name_en'], 'Legendary Resistance')
        self.assertEqual(self.creature.statblock_json['reactions'], self.original['reactions'])
        self.assertEqual(self.creature.statblock_json['spell_refs'], ['cura'])

    def test_stale_form_and_renamed_imported_ability_do_not_write(self):
        form = self.form()
        self.creature.nome = 'Unicórnio alterado'
        self.creature.save(update_fields=['nome'])
        stale = self.client.post(self.url, form)
        self.assertIn('e=conflito', stale['Location'])
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.statblock_json, self.original)
        fresh = self.form()
        fresh['tracos'] = 'Novo nome | Resiste. | defesa:lenda'
        rejected = self.client.post(self.url, fresh)
        self.assertIn('e=estrutura', rejected['Location'])
        self.creature.refresh_from_db()
        self.assertEqual(self.creature.statblock_json, self.original)

    def test_existing_tags_json_is_updated_without_creating_duplicate_tags(self):
        block = deepcopy(self.original)
        block['traits'][0]['tags_json'] = ['defesa:antiga']
        self.creature.statblock_json = block
        self.creature.save(update_fields=['statblock_json'])
        form = self.form()
        form['tracos'] = 'Resistência Lendária | Resiste. | defesa:nova'
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        self.creature.refresh_from_db()
        trait = self.creature.statblock_json['traits'][0]
        self.assertEqual(trait['tags_json'], ['defesa:nova'])
        self.assertNotIn('tags', trait)
