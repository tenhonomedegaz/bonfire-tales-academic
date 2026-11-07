"""Inline class and race requests preserve published rules on broken input."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbClasse, TbClassehabilidade, TbRaca, TbTracoracial


class ClassRacePayloadIntegrityTests(TestCase):
    def setUp(self):
        classe = TbClasse.objects.create(nome='Classe Íntegra', slug='classe-integra')
        self.feature = TbClassehabilidade.objects.create(
            id_classe=classe, nome='Recurso Íntegro', niveladquirido=1,
            descricao='Habilidade publicada.', tags_json=['editorial:classe'],
        )
        self.race = TbRaca.objects.create(
            nome='Povo Íntegro', slug='povo-integro', tagline='Lema publicado.',
            imagem_url='https://example.com/povo.png', lore_presentation='Lore publicada.',
            lore_roleplay='Interpretação publicada.', lore_society='Sociedade publicada.',
        )
        self.trait = TbTracoracial.objects.create(
            id_raca=self.race, nome='Traço Íntegro', nivel_requisito=1,
            pre_requisito='Nível 1', descricao='Traço publicado.',
            tags_json=['editorial:traco'], talento_racial=True,
        )
        self.targets = (
            (self.feature, reverse('wiki_update_class_feature', args=[self.feature.pk])),
            (self.race, reverse('wiki_update_race', args=[self.race.pk])),
            (self.trait, reverse('wiki_update_racial_trait', args=[self.trait.pk])),
        )
        editor = get_user_model().objects.create_user('editor-integridade-classe-raca', is_staff=True)
        editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home', codename__in=(
                'change_tbclassehabilidade', 'change_tbraca', 'change_tbtracoracial',
            ),
        ))
        self.client.force_login(editor)

    @staticmethod
    def audit_count(obj):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk),
        ).count()

    def test_invalid_json_does_not_erase_published_content_or_create_audit(self):
        for obj, url in self.targets:
            original = {field: getattr(obj, field) for field in (
                ('descricao', 'tags_json') if obj is not self.race
                else ('tagline', 'imagem_url', 'lore_presentation', 'lore_roleplay', 'lore_society')
            )}
            for payload in ('{', '[]', '{}', '', '{"unknown": 1}'):
                with self.subTest(model=type(obj).__name__, payload=payload):
                    response = self.client.post(url, payload, content_type='application/json')
                    self.assertEqual(response.status_code, 400)
                    obj.refresh_from_db()
                    self.assertEqual({field: getattr(obj, field) for field in original}, original)
                    self.assertEqual(self.audit_count(obj), 0)

    def test_partial_edits_preserve_other_fields_and_reach_public_pages(self):
        changes = (
            (self.feature, self.targets[0][1], {'descricao': 'Habilidade revisada.'}),
            (self.race, self.targets[1][1], {'imagem_foco_x': 35}),
            (self.trait, self.targets[2][1], {'descricao': 'Traço revisado.'}),
        )
        for obj, url, payload in changes:
            with self.subTest(model=type(obj).__name__):
                response = self.client.post(url, json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                obj.refresh_from_db()
                self.assertEqual(self.audit_count(obj), 1)
        self.assertEqual(self.feature.tags_json, ['editorial:classe'])
        self.assertEqual(self.race.lore_presentation, 'Lore publicada.')
        self.assertEqual(self.race.imagem_url, 'https://example.com/povo.png')
        self.assertEqual(self.race.imagem_foco_x, 35)
        self.assertEqual(self.trait.pre_requisito, 'Nível 1')
        self.assertTrue(self.trait.talento_racial)
        self.assertEqual(self.trait.tags_json, ['editorial:traco'])
        self.client.logout()
        self.assertContains(self.client.get(reverse('classe_detail', args=['classe-integra'])),
                            'Habilidade revisada.')
        race_page = self.client.get(reverse('raca_detail', args=['povo-integro']))
        self.assertContains(race_page, 'Lore publicada.')
        self.assertContains(race_page, 'Traço revisado.')

    def test_explicit_empty_fields_can_still_be_cleared(self):
        for obj, url, payload in (
            (self.feature, self.targets[0][1], {'descricao': '', 'tags_json': []}),
            (self.race, self.targets[1][1], {'tagline': '', 'imagem_url': '', 'lore_roleplay': ''}),
            (self.trait, self.targets[2][1], {'pre_requisito': '', 'descricao': '', 'tags_json': []}),
        ):
            with self.subTest(model=type(obj).__name__):
                self.assertEqual(self.client.post(
                    url, json.dumps(payload), content_type='application/json',
                ).status_code, 200)
                obj.refresh_from_db()
                self.assertEqual(self.audit_count(obj), 1)
        self.assertEqual(self.feature.descricao, '')
        self.assertEqual(self.feature.tags_json, [])
        self.assertIsNone(self.race.tagline)
        self.assertIsNone(self.race.imagem_url)
        self.assertEqual(self.race.lore_roleplay, '')
        self.assertEqual(self.race.lore_presentation, 'Lore publicada.')
        self.assertIsNone(self.trait.pre_requisito)
        self.assertEqual(self.trait.descricao, '')
        self.assertEqual(self.trait.tags_json, [])
