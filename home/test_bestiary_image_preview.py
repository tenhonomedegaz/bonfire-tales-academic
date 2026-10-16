from django.test import SimpleTestCase

from .bestiary_image_preview import preview_images


class BestiaryImagePreviewTests(SimpleTestCase):
    def test_matches_original_name_and_edition_without_touching_owned_art(self):
        source = [{'Name': 'Adult Bronze Dragon', 'Source': "MM'25", 'Page': '59'},
                  {'Name': 'Adult Bronze Dragon', 'Source': 'MPMM', 'Page': '80'}]
        creatures = [{'pk': 1, 'fields': {'slug': 'bronze', 'comunidade': False,
                      'autor': None, 'imagem_url': None,
                      'statblock_json': {'name_en': 'Adult Bronze Dragon'}}},
                     {'pk': 2, 'fields': {'slug': 'owned', 'imagem_url': '/media/owned.png',
                      'statblock_json': {'name_en': 'Adult Bronze Dragon'}}}]
        assets = {'XMM': [{'name': 'Adult Bronze Dragon.webp', 'sha': 'abc',
                           'size': 123, 'path': 'bestiary/XMM/Adult Bronze Dragon.webp'}]}
        result = preview_images(source, creatures, assets)
        self.assertEqual(result['summary'], {'ambiguous_source': 1})
        self.assertEqual([row['slug'] for row in result['records']], ['bronze'])
        result = preview_images(source[:1], creatures, assets)
        self.assertEqual(result['summary'], {'candidate_exact': 1})
        self.assertEqual(result['records'][0]['candidates'][0]['sha'], 'abc')
        self.assertEqual(result['rights_status'], 'unreviewed')

    def test_missing_and_ambiguous_files_remain_for_review(self):
        source = [{'Name': 'Froghemoth', 'Source': 'MPMM', 'Page': '130'}]
        creature = [{'pk': 1, 'fields': {'slug': 'froghemoth', 'imagem_url': None,
                    'statblock_json': {'name_en': 'Froghemoth'}}}]
        self.assertEqual(preview_images(source, creature, {})['summary'],
                         {'source_unavailable': 1})
        self.assertEqual(preview_images(source, creature, {'MPMM': []})['summary'],
                         {'no_exact_image': 1})
        assets = {'MPMM': [{'name': 'Froghemoth.png'}, {'name': 'Froghemoth.webp'}]}
        self.assertEqual(preview_images(source, creature, assets)['summary'],
                         {'ambiguous_image': 1})
