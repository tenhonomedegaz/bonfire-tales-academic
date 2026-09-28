import json
from io import StringIO

from django.core.management import call_command
from django.urls import reverse

from . import views
from .hunter_catalog import compose_order_revision
from .models import TbPersonagem, TbPersonagemClasse, TbPersonagemCacador, TbSubclasse
from .test_criador import _CriadorBase
from .test_hunter_catalog import HunterCatalogTests


class HunterOrderLevelUpTests(_CriadorBase):
    setup_catalog = HunterCatalogTests.setup_catalog

    def setUp(self):
        self.setup_catalog()
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        self.order_ids = json.loads(output.getvalue())['order_ids']
        self.ruleset = compose_order_revision(self.new, class_id=self.classe.pk,
                                               order_ids=self.order_ids)
        self.user = self._novo_usuario('order-levelup')
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Novo Caçador', nivel=3)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.classe, nivel=3, principal=True)
        self.profile = TbPersonagemCacador.objects.create(personagem_classe=self.pc,
            ruleset=self.ruleset, ability='int')

    def test_sealed_revision_contains_complete_order_and_secret_content(self):
        from pathlib import Path
        from django.utils.text import slugify
        from .content_versions import resolve_content
        from .models import TbClassehabilidade
        from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog
        source = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf8'))
        rework = resolve_content(self.ruleset, 'hunter-rework',
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.assertEqual((len(rework['progression']), len(rework['orders']),
                          len(rework['secrets']), len(rework['exclusive_secrets'])),
                         (20, 8, 30, 8))
        self.assertEqual(len(rework['spell_grants']), 83)
        self.assertEqual({row['order'] for row in rework['exclusive_secrets']},
                         set(self.order_ids))
        self.assertEqual({row['line'] for row in rework['secrets']},
                         {'Alquimia e Poções', 'Armadilhas e Emboscadas',
                          'Conhecimentos Ancestrais (Sinais)'})
        frozen = VersionedClassCatalog(self.ruleset, self.classe.pk)
        indexed = {(feature.id_subclasse_id, feature.nome, feature.niveladquirido): feature
                   for feature in frozen.collections[TbClassehabilidade]
                   if feature.id_subclasse_id in self.order_ids.values()}
        order_features = [row for row in source['features'] if row['order']]
        self.assertEqual(len(indexed), len(order_features))
        for row in order_features:
            feature = indexed[(self.order_ids[slugify(row['order'])],
                               row['name'], row['level'])]
            self.assertEqual(feature.descricao, row['text'])

    def test_new_order_options_use_frozen_text_and_reject_legacy_identity(self):
        pending = views._pendencias_nivel(self.person, self.classe.pk)
        self.assertTrue(pending['subclasse'])
        self.assertEqual({row['id'] for row in pending['subclasses']},
                         set(self.order_ids.values()))
        self.assertTrue(all(row['descricao'] for row in pending['subclasses']))
        original = TbSubclasse.objects.get(pk=116)
        self.assertEqual(views._lvl_aplicar_subclasse(self.person,
            {'classe': self.classe.pk, 'subclasse': original.pk}), [views._ERR_SUB_INVALIDA])
        choice = self.order_ids['ordem-do-enxame']
        name = next(row['nome'] for row in pending['subclasses'] if row['id'] == choice)
        TbSubclasse.objects.filter(pk=choice).update(nome='Nome vivo alterado')
        frozen = views._pendencias_nivel(self.person, self.classe.pk)
        self.assertEqual(next(row['nome'] for row in frozen['subclasses']
                              if row['id'] == choice), name)
        self.client.force_login(self.user)
        page = self.client.get(reverse('personagem_subir_nivel', args=[self.person.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertEqual({row['id'] for row in page.context['pend']['subclasses']},
                         set(self.order_ids.values()))
        self.assertEqual(views._lvl_aplicar_subclasse(self.person,
            {'classe': self.classe.pk, 'subclasse': choice}), [])
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.id_subclasse_id, choice)

    def test_unbound_hunter_keeps_only_legacy_order_choices(self):
        self.profile.delete()
        pending = views._pendencias_nivel(self.person, self.classe.pk)
        self.assertEqual(len(pending['subclasses']), 6)
        self.assertFalse(set(self.order_ids.values()) &
                         {row['id'] for row in pending['subclasses']})
        self.assertEqual(views._lvl_aplicar_subclasse(self.person,
            {'classe': self.classe.pk,
             'subclasse': self.order_ids['ordem-do-enxame']}), [views._ERR_SUB_INVALIDA])
        self.assertEqual(views._lvl_aplicar_subclasse(self.person,
            {'classe': self.classe.pk, 'subclasse': 116}), [])

    def test_preview_apply_and_linked_sheet_use_selected_order(self):
        choice = self.order_ids['ordem-do-enxame']
        self.client.force_login(self.user)
        body = {'acoes': [{'tipo': 'subclasse', 'payload': {
            'classe': self.classe.pk, 'subclasse': choice}}]}
        preview = self.client.post(reverse('personagem_levelup_preview', args=[self.person.pk]),
                                   data=body, content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()['ready'], preview.json())
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.id_subclasse_id)
        applied = self.client.post(reverse('personagem_levelup_aplicar', args=[self.person.pk]),
                                   data=body, content_type='application/json')
        self.assertEqual(applied.status_code, 200, applied.content)
        self.assertTrue(applied.json()['ok'])
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.id_subclasse_id, choice)
        sheet = self.client.get(reverse('hunter_sheet', args=[self.person.pk]))
        self.assertEqual(sheet.status_code, 200)
        self.assertContains(sheet, 'Habilidades da revisão')
        self.assertContains(sheet, 'Ordem do Enxame')
        order_features = [feature for feature in sheet.context['sheet']['features']
                          if feature['origem'] == 'subclasse']
        self.assertTrue(order_features)
        self.assertContains(sheet, order_features[0]['nome'])
