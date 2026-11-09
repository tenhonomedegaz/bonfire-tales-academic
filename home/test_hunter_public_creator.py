import json

from django.test import override_settings
from django.urls import reverse

from .models import TbAntecedente, TbClassPublication, TbClasse, TbPersonagem, TbPersonagemCacador, TbRaca
from .test_creator_hunter_binding import CreatorHunterBindingTests
from .test_criador import _CriadorBase


class HunterPublicCreatorTests(_CriadorBase):
    setup_creation = CreatorHunterBindingTests.setup_creation
    valid_payload = CreatorHunterBindingTests.valid_payload

    def test_s10_published_hunter_orders_preview_without_persistence(self):
        from .class_revision_editor import create_class_revision
        from .hunter_rework import catalog
        from .models import TbClassehabilidade, TbRecursoclasse, TbSubclasse
        from .pathbuilder import catalogos, default_build
        from .versioned_classes import VersionedClassCatalog

        orders = catalog()['orders']
        expected = {order['id']: order['name'] for order in orders}
        self.assertEqual(len(expected), 8)
        self.setup_creation()
        frozen = VersionedClassCatalog(self.ruleset, self.classe.pk)
        legacy = {row.pk for row in frozen.collections[TbSubclasse]
                  if row.slug not in expected}
        changes = [
            {'model': model._meta.label_lower, 'action': 'remove', 'pk': row.pk}
            for model in (TbClassehabilidade, TbRecursoclasse)
            for row in frozen.collections[model] if row.id_subclasse_id in legacy
        ] + [
            {'model': TbSubclasse._meta.label_lower, 'action': 'remove', 'pk': pk}
            for pk in sorted(legacy)
        ]
        existing = {row.slug for row in frozen.collections[TbSubclasse]}
        for slug, name in expected.items():
            if slug not in existing:
                row = TbSubclasse.objects.create(id_classe=self.classe, slug=slug, nome=name)
                changes.append({'model': TbSubclasse._meta.label_lower,
                                'action': 'add', 'pk': row.pk})

        self.ruleset = create_class_revision(self.ruleset.checksum, self.classe.pk,
                                             changes, presentation_source='catalog')
        self.assertEqual(TbSubclasse.objects.filter(pk__in=legacy).count(), len(legacy))
        TbClassPublication.objects.create(id_classe=self.classe, ruleset=self.ruleset)
        self.client.force_login(self.user)
        before = TbPersonagem.objects.count()
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum,
                               CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum}):
            published = next(row for row in catalogos()['classes']
                             if row['slug'] == 'cacador')
            self.assertEqual({row['slug'] for row in published['subclasses']}, set(expected))
            for level in (1, 20):
                with self.subTest(level=level):
                    build = default_build(self.payload)
                    build['classes'][0].update(nivel=level,
                        subclasse='' if level == 1 else orders[0]['id'])
                    response = self.client.post(reverse('pathbuilder_preview'),
                        data=json.dumps({'base': self.payload, 'build': build}),
                        content_type='application/json')
                    self.assertEqual(response.status_code, 200, response.content[:500])
                    self.assertEqual(response.json()['build']['nivel'], level)
            for slug, name in expected.items():
                with self.subTest(order=slug):
                    build = default_build(self.payload)
                    build['classes'][0].update(nivel=3, subclasse=slug)
                    response = self.client.post(reverse('pathbuilder_preview'),
                        data=json.dumps({'base': self.payload, 'build': build}),
                        content_type='application/json')
                    self.assertEqual(response.status_code, 200, response.content[:500])
                    preview = response.json()['build']
                    self.assertEqual(preview['nivel'], 3)
                    self.assertEqual(preview['classes'][0]['subclasse'], name)
                    self.assertIn(name, preview['ficha_html'])
        self.assertEqual(TbPersonagem.objects.count(), before)

    def test_pathbuilder_hunter_entry_and_preview_keep_published_class(self):
        from .class_revision_editor import create_class_revision
        from .pathbuilder import default_build
        from .versioned_classes import VersionedClassCatalog
        from .models import TbClassehabilidade, TbSubclasse

        self.setup_creation()
        _, errors = self.valid_payload('int')
        self.assertEqual(errors, [])
        feature = TbClassehabilidade.objects.filter(id_classe=self.classe).first()
        self.assertIsNotNone(feature)
        self.ruleset = create_class_revision(self.ruleset.checksum, self.classe.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'update',
             'pk': feature.pk, 'fields': {'descricao': '## Revisao publicada no laboratorio'}}
        ], presentation_source='catalog')
        TbClassPublication.objects.create(id_classe=self.classe, ruleset=self.ruleset)
        self.client.force_login(self.user)
        before = TbPersonagem.objects.count()
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum,
                               CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum}):
            TbClasse.objects.filter(pk=self.classe.pk).update(
                nome='Caçador vivo alterado', tags_json=[])
            live_only = TbSubclasse.objects.create(
                id_classe=self.classe, slug='ordem-so-no-catalogo-vivo',
                nome='Ordem só no catálogo vivo')
            entry = self.client.get(reverse('pathbuilder') + '?hunter=1')
            self.assertEqual(entry.status_code, 200, entry.content[:300])
            self.assertEqual([row['slug'] for row in entry.context['catalogos']['classes']],
                             ['cacador'])
            self.assertContains(entry, 'cf-hunter-ability')
            laboratory = self.client.get(reverse('pathbuilder_laboratorio'))
            self.assertEqual(laboratory.status_code, 200, laboratory.content[:300])
            hunter = next(row for row in laboratory.context['catalogos']['classes']
                          if row['slug'] == 'cacador')
            self.assertEqual(hunter['ruleset_checksum'], self.ruleset.checksum)
            self.assertNotIn(live_only.slug,
                             {row['slug'] for row in hunter['subclasses']})
            start = self.client.post(reverse('pathbuilder_iniciar'),
                data=json.dumps(self.payload), content_type='application/json')
            self.assertEqual(start.status_code, 200, start.content)
            preview = self.client.post(reverse('pathbuilder_preview'),
                data=json.dumps({'base': self.payload,
                                 'build': default_build(self.payload)}),
                content_type='application/json')
            self.assertEqual(preview.status_code, 200, preview.content[:500])
            self.assertEqual(preview.json()['build']['classes'][0]['classe'], self.classe.nome)
            published_subclass = next(iter(VersionedClassCatalog(
                self.ruleset, self.classe.pk).collections[TbSubclasse]), None)
            if published_subclass is not None:
                advanced = default_build(self.payload)
                advanced['classes'][0].update(
                    nivel=3, subclasse=published_subclass.slug)
                advanced_preview = self.client.post(reverse('pathbuilder_preview'),
                    data=json.dumps({'base': self.payload, 'build': advanced}),
                    content_type='application/json')
                self.assertEqual(advanced_preview.status_code, 200,
                                 advanced_preview.content[:500])
                self.assertEqual(advanced_preview.json()['build']['classes'][0]['subclasse'],
                                 published_subclass.nome)
                for level, slots in ((4, 1), (19, 5)):
                    with self.subTest(level=level):
                        advanced['classes'][0]['nivel'] = level
                        asi_preview = self.client.post(reverse('pathbuilder_preview'),
                            data=json.dumps({'base': self.payload, 'build': advanced}),
                            content_type='application/json')
                        self.assertEqual(asi_preview.status_code, 200,
                                         asi_preview.content[:500])
                        budget = asi_preview.json()['build']['orcamento']
                        self.assertEqual(budget['asi_slots'], slots)
                        self.assertEqual(budget['pontos_disponiveis'], slots * 2)
        self.assertEqual(TbPersonagem.objects.count(), before)
    def test_configured_revision_serves_catalog_preview_and_create_without_resolver_patch(self):
        self.setup_creation()
        self.assertEqual(self.valid_payload('int')[1], [])
        self.payload['ruleset'] = 'cliente-nao-escolhe-revisao'
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum,
                               CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum}):
            TbClasse.objects.filter(pk=self.classe.pk).update(nome='Classe viva alterada', tags_json=[])
            TbRaca.objects.filter(slug='anao').update(nome='Raça viva alterada')
            TbAntecedente.objects.filter(slug='acolito').update(nome='Antecedente vivo alterado')
            default_page = self.client.get(reverse('criacao_ficha'))
            self.assertEqual(default_page.status_code, 200)
            common_hunter = next(c for c in default_page.context['catalogos']['classes']
                                 if c['slug'] == 'cacador')
            self.assertTrue(common_hunter['hunter_rework'])
            self.assertEqual(common_hunter['nome'], self.classe.nome)
            page = self.client.get(reverse('criacao_ficha') + '?hunter=1')
            self.assertEqual(page.status_code, 200)
            self.assertEqual([c['slug'] for c in page.context['catalogos']['classes']], ['cacador'])
            hunter = next(c for c in page.context['catalogos']['classes'] if c['slug'] == 'cacador')
            self.assertTrue(hunter['hunter_rework'])
            self.assertEqual(hunter['nome'], self.classe.nome)
            race = next(r for r in page.context['catalogos']['racas'] if r['slug'] == 'anao')
            background = next(a for a in page.context['catalogos']['antecedentes'] if a['slug'] == 'acolito')
            self.assertNotEqual(race['nome'], 'Raça viva alterada')
            self.assertNotEqual(background['nome'], 'Antecedente vivo alterado')
            self.assertEqual(next(r for r in default_page.context['catalogos']['racas'] if r['slug'] == 'anao')['nome'], 'Raça viva alterada')
            self.assertContains(page, 'cf-hunter-ability')
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            self.assertTrue(preview['ready'], preview)
            self.assertEqual(preview['erros'], [])
            self.assertFalse(TbPersonagem.objects.exists())
            response = self._post_criar(self.user, self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.pv_maximo, preview['preview']['pv'])
        self.assertEqual(TbPersonagemCacador.objects.get(
            personagem_classe__id_personagem=person).ruleset_id, self.ruleset.pk)

    @override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='', CLASS_CATALOG_RULESETS={})
    def test_client_cannot_select_revision_when_server_has_not_published_it(self):
        self.setup_creation()
        TbClassPublication.objects.filter(id_classe=self.classe).delete()
        self.client.force_login(self.user)
        self.payload['ruleset'] = self.ruleset.pk
        page = self.client.get(reverse('criacao_ficha'))
        self.assertEqual(page.status_code, 200)
        hunter = next(c for c in page.context['catalogos']['classes'] if c['slug'] == 'cacador')
        self.assertFalse(hunter['hunter_rework'])
        response = self._post_criar(self.user, self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_missing_ability_and_invalid_published_checksum_fail_without_writes(self):
        self.setup_creation()
        self.assertEqual(self.valid_payload('wis')[1], [])
        self.client.force_login(self.user)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=self.ruleset.checksum,
                               CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum}):
            self.payload['hunter_ability'] = ''
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=json.dumps(self.payload), content_type='application/json').json()
            self.assertFalse(preview['ready'])
            self.assertIn('Ca', ' '.join(preview['erros']))
            response = self._post_criar(self.user, self.payload)
            self.assertEqual(response.status_code, 400)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='0' * 64,
                               CLASS_CATALOG_RULESETS={'cacador': '0' * 64}):
            creator = self.client.get(reverse('criacao_ficha'))
            self.assertEqual(creator.status_code, 200)
            self.assertNotIn('cacador', {row['slug'] for row in creator.context['catalogos']['classes']})
            self.assertEqual(self.client.get(reverse('criacao_ficha') + '?hunter=1').status_code, 503)
            page = self.client.get(reverse('pathbuilder'))
            self.assertEqual(page.status_code, 200)
            available = {row['slug'] for row in page.context['catalogos']['classes']}
            self.assertNotIn('cacador', available)
            self.assertIn('guerreiro', available)
            self.assertEqual(self.client.get(reverse('pathbuilder') + '?hunter=1').status_code, 503)
            self.assertEqual(self.client.get(reverse('pathbuilder_laboratorio')).status_code, 200)
            self.assertEqual(self._post_criar(self.user, self.payload).status_code, 503)
        self.assertFalse(TbPersonagem.objects.exists())
        self.assertFalse(TbPersonagemCacador.objects.exists())
